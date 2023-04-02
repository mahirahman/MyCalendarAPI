from datetime import datetime, timedelta, date
from io import BytesIO
from calendar import monthrange
from collections import defaultdict
import sys
import re
import sqlite3
from flask import Flask, request, Response
from flask_restx import Api, Resource, fields, reqparse
import pandas as pd
import matplotlib.pyplot as plt
import requests
from util.sql import execute_query
import util.validation as validation
import util.constants as const

if len(sys.argv) != 3:
    print(const.USAGE_MESSAGE)
    sys.exit(1)
au_df = pd.read_csv(sys.argv[2])
georef_df = pd.read_csv(sys.argv[1], delimiter=';')

execute_query(const.SCHEMA)
app = Flask(__name__)
api = Api(app,
          default=const.API_NAME,
          title=const.API_NAME,
          description=const.API_DESCRIPTION,)

# Schema of an event payload
event_model = api.model('Event', {
    "name": fields.String(example="Birthday Party"),
    "date": fields.Date(example="2000-01-01"),
    "from": fields.String(example="16:00:00"),
    "to": fields.String(example="20:00:00"),
    "location": fields.Nested(api.model('Location', {
        'street': fields.String(example="215B Night Av"),
        'suburb': fields.String(example="Kensington"),
        'state': fields.String(example="NSW"),
        'post-code': fields.String(example="2033")
    })),
    "description": fields.String(example="The cake is a lie")
})


@api.route('/events')
class CreateEvent(Resource):

    order_parser = reqparse.RequestParser()
    order_parser.add_argument(
        'order',
        type=str,
        help="Sort order - comma-separated value to sort the list based on the given criteria.\
        The string consists of two parts: the first part is a special character '+' or '-' where\
        '+' indicates ordering ascendingly, and '-' indicates ordering descendingly. The second\
        part is an attribute name which is one of {id, name, datetime, date, time_from, time_to,\
        street, suburb, state, post_code, description, last_update}",
        default='+id')
    order_parser.add_argument('page', type=int, help='Page number', default=1)
    order_parser.add_argument('size', type=int, help='Page size', default=10)
    order_parser.add_argument(
        'filter',
        type=str,
        help='Fields to include in response - comma-separated value (combination of: id, name,\
            date, from, to, and location), and shows what attribute should be shown for each\
            event accordingly.',
        default='id,name')

    @api.response(201, 'Event Created Successfully')
    @api.response(400, 'Validation Error')
    @api.doc(description="Create A New Event")
    @api.expect(event_model, validate=True)
    def post(self):
        request_data = request.json

        # Check request data contains all required fields
        if not const.FIELDS.issubset(
            request_data.keys()) or not const.LOCATION_FIELDS.issubset(
            request_data.get(
                'location',
                {}).keys()):
            return {"Error": "Missing required fields"}, 400

        # Validate request data
        validation_errors = validation.all_data(request_data)
        if validation_errors:
            return {"Errors": validation_errors}, 400

        overlap_query = "SELECT * FROM events WHERE date = ? AND time_from < ? AND time_to > ?"
        overlap_params = (request_data['date'],
                          request_data['to'], request_data['from'])
        is_overlap = execute_query(overlap_query, overlap_params)

        if is_overlap:
            return {"Error": "Event overlaps with another event"}, 400
        event_id = execute_query("SELECT COUNT(*) FROM events")[0][0] + 1
        curr_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        insert_query = "INSERT INTO events VALUES(NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        insert_params = (
            request_data['name'],
            request_data['date'],
            request_data['from'],
            request_data['to'],
            request_data['location']['street'],
            request_data['location']['suburb'],
            request_data['location']['state'],
            request_data['location']['post-code'],
            request_data['description'],
            curr_time)
        execute_query(insert_query, insert_params)
        return {'id': int(event_id), 'last-update': curr_time,
                '_links': {'self': {'href': f'/events/{str(event_id)}'}}}, 201

    @api.response(200, 'Successfully Retrieved All Events')
    @api.response(400, 'Validation Error')
    @api.response(404, 'Events Not Found')
    @api.doc(description="Get All Events")
    @api.expect(order_parser)
    def get(self):
        args = self.order_parser.parse_args()
        arg_order = args['order']
        arg_page = args['page']
        arg_size = args['size']
        arg_filter = args['filter']

        # Validate arg_order
        order_pattern = r'^([\+\-][a-zA-Z_]+)(,[\+\-][a-zA-Z_]+)*$'
        if not re.match(order_pattern, arg_order):
            return {"Error": "Invalid order query"}, 400

        # Validate arg_page
        if arg_page < 1:
            return {"Error": "Invalid page query"}, 400

        # Validate arg_size
        if arg_size < 1:
            return {"Error": "Invalid size query"}, 400

        # Validate arg_filter
        filter_pattern = r'^[a-zA-Z_]+(,[a-zA-Z_]+)*$'
        if not re.match(
                filter_pattern,
                arg_filter) or not const.FILTER_FIELDS.issuperset(
                arg_filter.split(',')):
            return {"Error": "Invalid filter query"}, 400

        order_criteria = []
        for order in arg_order.split(','):
            attr_name = order[1:]
            if order.startswith('+'):
                order_criteria.append(f"{attr_name} ASC")
            elif order.startswith('-'):
                order_criteria.append(f"{attr_name} DESC")
        order_string = ', '.join(order_criteria)

        try:
            result = execute_query(
                f"SELECT {arg_filter} FROM 'events'\
                ORDER BY {order_string}\
                LIMIT {arg_size}\
                OFFSET {(arg_page - 1) * arg_size}")
        except sqlite3.Error as e:
            return str(e), 400
        if not result:
            return {"Error": f"No events found on page {arg_page}"}, 404

        events = []
        for row in result:
            event = {}
            for i, field in enumerate(arg_filter.split(',')):
                event[field] = row[i]
            events.append(event)
        return {
            "page": arg_page,
            "page-size": arg_size,
            "events": events,
            "_links": {
                "self": {
                    "href": f"/events?order={arg_order}&page={arg_page}\
                        &size={arg_size}&filter={arg_filter}",
                },
                "next": {
                    "href": f"/events?order={arg_order}&page={arg_page + 1}\
                        &size={arg_size}&filter={arg_filter}",
                }}}


@api.route('/events/<int:id>')
@api.param('id', 'The Event identifier')
class Events(Resource):

    def get_start_time_in_dataseries(self):
        # Convert the current time to format: 16:29:00
        curr_time = datetime.now().strftime('%H:%M:%S')
        init_time = datetime.strptime('11:00:00', '%H:%M:%S').time()
        # Find the time difference between curr_time and CONST_TIME
        time_diff = datetime.combine(datetime.today(), datetime.strptime(str(
            curr_time), '%H:%M:%S').time()) - datetime.combine(datetime.today(), init_time)
        # Convert the time difference to hours
        time_diff_hours = time_diff.total_seconds() / 3600
        # Calculate the starting time for the first item in the dataseries list
        starting_time = (
            datetime.combine(
                datetime.today(),
                datetime.time(
                    datetime(
                        1,
                        1,
                        1,
                        11,
                        0))) +
            timedelta(
                hours=int(
                    time_diff_hours //
                    3) *
                3)).time()
        return starting_time

    @api.response(200, 'Successfully Retrieved Event')
    @api.response(404, 'Event Not Found')
    @api.response(500, 'Error Getting Data From External API')
    @api.doc(description="Get An Event By ID")
    def get(self, id):
        event = execute_query(
            "SELECT * FROM events WHERE id = ?", (id,))
        if not event:
            return {"Error": f"Event {id} doesn't exist"}, 404
        else:
            event = event[0]
        previous_event = execute_query(
            "SELECT * FROM events WHERE date < ? OR (date = ? AND time_to < ?)\
                ORDER BY date DESC, time_to DESC LIMIT 1",
            (event[2],
             event[2],
                event[3]))
        next_event = execute_query(
            "SELECT * FROM events WHERE date > ? OR (date = ? AND time_from > ?)\
                ORDER BY date ASC, time_from ASC LIMIT 1",
            (event[2],
             event[2],
                event[4]))

        # Get links data
        links = {
            'self': {
                'href': f'/events/{str(id)}'
            }
        }
        if previous_event:
            links['previous'] = {
                'href': f'/events/{str(previous_event[0][0])}'}
        if next_event:
            links['next'] = {'href': f'/events/{str(next_event[0][0])}'}

        # Get holiday and weekend data
        metadata = {}
        metadata['weekend'] = datetime.strptime(
            event[2], '%Y-%m-%d').date().weekday() >= 5
        url = f"https://date.nager.at/api/v2/publicholidays/{datetime.now().year}/AU"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            for holiday in data:
                if holiday['date'] == event[2]:
                    metadata['holiday'] = holiday['name']
                    break
        else:
            return {"Error": "Error getting holiday data from NagerDate"}, 500

        # Get weather data
        event_date_time = datetime.strptime(event[2], '%Y-%m-%d').date()
        date_diff = (event_date_time - datetime.today().date()).days
        start_time = self.get_start_time_in_dataseries()
        start_datetime = datetime.combine(datetime.today().date(), start_time)
        from_time = datetime.strptime(event[3], '%H:%M:%S').time()
        event_datetime = datetime.combine(event_date_time, from_time)
        # Check if event is within 7 days and start_time does not take place
        # before event_datetime
        if date_diff <= 7 and date_diff >= 0 and event_datetime >= start_datetime:
            # Get lat and lng from Suburb and State
            df = georef_df[['Geo Point', 'Official Name Suburb',
                            'Official Name State']].dropna()
            rows = df[df['Official Name Suburb'].str.contains(
                event[6]) & df['Official Name State'].str.contains(const.STATE_ABBREVIATIONS[event[7]])]
            # Check if row dataframe is not empty
            if not rows.empty:
                # Get the first row from row dataframe
                row = rows.iloc[0]
                lat = row['Geo Point'].split(',')[0].replace(' ', '')
                lng = row['Geo Point'].split(',')[1].replace(' ', '')
                url = f"https://www.7timer.info/bin/civil.php?lon={lng}&lat={lat}&lang=en&ac=0&unit=metric&output=json"
                response = requests.get(url)
                if response.status_code == 200:
                    dataseries = response.json().get('dataseries')
                    first_element = datetime.combine(
                        datetime.today().date(), start_time)
                    # Keep adding 3 hours to first_element until the date is
                    # equal to event[2] and time is greater than event[3]
                    count = 0
                    while first_element.date() < event_date_time or first_element.time() <= from_time:
                        first_element += timedelta(hours=3)
                        count += 1
                    metadata['cloud-cover'] = const.CLOUD_COVER.get(
                        dataseries[count].get('cloudcover'))
                    metadata['precepitation-type'] = const.PRECEPICTION_TYPE.get(
                        dataseries[count].get('prec_type'))
                    prec_amount = const.PRECEPICTION_RATE.get(
                        dataseries[count].get('prec_amount'))
                    if prec_amount != 'None':
                        metadata['precepitation-rate'] = prec_amount
                    metadata['wind-speed'] = const.WEATHER_SPEED.get(
                        dataseries[count].get('wind10m').get('speed'))
                    metadata['weather'] = const.WEATHER_CONDITION.get(
                        dataseries[count].get('weather'))
                    metadata['humidity'] = dataseries[count].get('rh2m')
                    metadata['temperature'] = f"{dataseries[count].get('temp2m')} °C"
                else:
                    return {
                        "Error": "Error getting weather data from 7Timer"}, 500

        return {
            'id': event[0],
            'last-update': event[10],
            'name': event[1],
            'date': event[2],
            'from': event[3],
            'to': event[4],
            'location': {
                'street': event[5],
                'suburb': event[6],
                'state': event[7],
                'post-code': event[8]
            },
            'description': event[9],
            '_metadata': metadata,
            '_links': links
        }, 200

    @api.response(404, 'Event Was Not Found')
    @api.response(200, 'Event Deleted Successfully')
    @api.doc(description="Delete An Event By Its ID")
    def delete(self, id):
        event = execute_query("SELECT * FROM events WHERE id = ?", (id,))
        if not event:
            return {"Error": f"Event {id} doesn't exist"}, 404

        execute_query("DELETE FROM events WHERE id = ?", (id,))
        return {
            "message": f"The event with id {id} was removed from the database!", "id": id}, 200

    @api.response(404, 'Event Was Not Found')
    @api.response(200, 'Event Updated Successfully')
    @api.response(400, 'Validation Error')
    @api.doc(description="Update An Event By Its ID")
    @api.expect(event_model, validate=True)
    def patch(self, id):
        request_data = request.json
        event = execute_query("SELECT * FROM events WHERE id = ?", (id,))
        if not event:
            return {"Error": f"Event {id} doesn't exist"}, 404
        # Check if request_data contains only the fields that can be updated
        data_keys = set(request_data.keys())
        if not data_keys.issubset(const.FIELDS):
            return {"Error": "Invalid fields provided"}, 400
        location_data = request_data.get('location', {})
        if not set(location_data.keys()).issubset(const.LOCATION_FIELDS):
            return {"Error": "Invalid location fields provided"}, 400
        # Validate request data
        validation_errors = validation.all_data(request_data)
        if validation_errors:
            return {"Errors": validation_errors}, 400
        # Check if the event overlaps with another event
        overlap_query = "SELECT * FROM events WHERE date = ? AND time_from < ? AND time_to > ?"
        overlap_params = (
            request_data['date'] if 'date' in data_keys else execute_query(
                "SELECT date FROM events WHERE id = ?", (id,))[0][0],
            request_data['to'] if 'to' in data_keys else execute_query(
                "SELECT time_to FROM events WHERE id = ?", (id,))[0][0],
            request_data['from'] if 'from' in data_keys else execute_query(
                "SELECT time_from FROM events WHERE id = ?", (id,))[0][0],
        )

        is_overlap = execute_query(overlap_query, overlap_params)
        if is_overlap and is_overlap[0][0] != id:
            return {"Error": "Event overlaps with another event"}, 400

        # Update event in database
        curr_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        update_query = "UPDATE events SET name = ?, date = ?, time_from = ?, time_to = ?, street = ?, suburb = ?, state = ?, post_code = ?, description = ?, last_update = ? WHERE id = ?"
        update_params = (
            request_data['name'] if 'name' in data_keys else execute_query(
                "SELECT name FROM events WHERE id = ?", (id,))[0][0],
            request_data['date'] if 'date' in data_keys else execute_query(
                "SELECT date FROM events WHERE id = ?", (id,))[0][0],
            request_data['from'] if 'from' in data_keys else execute_query(
                "SELECT time_from FROM events WHERE id = ?", (id,))[0][0],
            request_data['to'] if 'to' in data_keys else execute_query(
                "SELECT time_to FROM events WHERE id = ?", (id,))[0][0],
            location_data['street'] if 'street' in location_data.keys() else execute_query(
                "SELECT street FROM events WHERE id = ?", (id,))[0][0],
            location_data['suburb'] if 'suburb' in location_data.keys() else execute_query(
                "SELECT suburb FROM events WHERE id = ?", (id,))[0][0],
            location_data['state'] if 'state' in location_data.keys() else execute_query(
                "SELECT state FROM events WHERE id = ?", (id,))[0][0],
            location_data['post-code'] if 'post-code' in location_data.keys() else execute_query(
                "SELECT post_code FROM events WHERE id = ?", (id,))[0][0],
            request_data['description'] if 'description' in data_keys else execute_query(
                "SELECT description FROM events WHERE id = ?", (id,))[0][0],
            curr_time,
            id
        )
        execute_query(update_query, update_params)

        return {
            "id": id,
            "last-update": curr_time,
            "_links": {
                "self": {
                    "href": f"/events/{id}"
                }
            }
        }, 200


@api.route('/events/statistics')
class Statistics(Resource):

    statistics_parser = reqparse.RequestParser()
    statistics_parser.add_argument(
        'format',
        type=str,
        required=True,
        help='Format of the statistics, can be either "json" or "image"')

    @api.expect(statistics_parser)
    @api.response(200, 'Successfully Retrieved Event Statistics')
    @api.response(400, 'Validation Error')
    @api.response(404, 'No Events Found')
    @api.doc(description="Get Event Statistics")
    def get(self):
        # Validate it is either json or image format
        args = self.statistics_parser.parse_args()
        if args['format'] not in ['json', 'image']:
            return {"Error": "Invalid format provided"}, 400

        # Total Number of events
        total_events = execute_query("SELECT COUNT(*) FROM events")[0][0]
        if total_events == 0:
            return {"Error": "No events found"}, 404
        # Total Number of events in current calendar Week (Today to Sunday)
        today = date.today()
        days_until_sunday = (6 - today.weekday()) % 7
        next_sunday = today + timedelta(days=days_until_sunday)
        total_events_current_week = execute_query(
            "SELECT COUNT(*) FROM events WHERE date BETWEEN ? AND ?",
            (datetime.now().strftime('%Y-%m-%d'),
             next_sunday))[0][0]

        # Total Number of events in current calendar Month (1st to the last day
        # of the month)
        first_day = today.replace(day=1)
        last_day = today.replace(day=28) + timedelta(days=4)

        # execute the SQL query to count the number of events in the current
        # month
        total_events_current_month = execute_query(
            "SELECT COUNT(*) FROM events WHERE date BETWEEN ? AND ?",
            (first_day.strftime('%Y-%m-%d'),
             last_day.strftime('%Y-%m-%d')))[0][0]

        # Number of events per day
        min_max_dates = execute_query(
            "SELECT MIN(date), MAX(date) FROM events")
        start_date_str = min_max_dates[0][0]
        end_date_str = min_max_dates[0][1]
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        query_result = execute_query(
            "SELECT date FROM events WHERE date BETWEEN ? AND ?", (start_date, end_date))
        events_per_day = defaultdict(int)
        for row in query_result:
            event_date = datetime.strptime(row[0], '%Y-%m-%d').date()
            events_per_day[event_date.strftime('%d-%m-%Y')] += 1

        if args['format'] == 'json':
            return {
                "total": total_events,
                "total-current-week": total_events_current_week,
                "total-current-month": total_events_current_month,
                "per-days": dict(events_per_day)
            }, 200
        else:
            current_year = datetime.now().year
            events_per_month = {}
            for month in range(1, 13):
                first_day = date(current_year, month, 1)
                last_day = date(current_year, month,
                                monthrange(current_year, month)[1])
                total_events_current_month = execute_query(
                    "SELECT COUNT(*) FROM events WHERE date BETWEEN ? AND ?",
                    (first_day.strftime('%Y-%m-%d'), last_day.strftime('%Y-%m-%d')))[0][0]
                events_per_month[first_day.strftime(
                    '%b')] = total_events_current_month

            fig, ax = plt.subplots()
            ax.bar(events_per_month.keys(), events_per_month.values())
            ax.set_xlabel('Month')
            ax.set_ylabel('Number of Events')
            ax.set_title(f'Events per Month in {current_year}')
            buffer = BytesIO()
            plt.savefig(buffer, format='png')
            buffer.seek(0)
            return Response(buffer.getvalue(), mimetype='image/png')


@api.route('/weather')
class Weather(Resource):

    date_parser = reqparse.RequestParser()
    date_parser.add_argument(
        'date',
        type=str,
        required=True,
        help='Date in the format "YYYY-MM-DD"')

    @api.expect(date_parser)
    @api.response(200, 'Successfully Retrieved Weather')
    @api.response(400, 'Validation Error')
    @api.doc(description="Get The Weather Of Each Capital City")
    def get(self):
        # Validate the date is in the correct format a
        args = self.date_parser.parse_args()
        if not validation.date(args['date']):
            return {"Error": "Invalid date format provided"}, 400
        # Validate the date is within 7 days
        # Get the lat and lng from all the popular locations and store them in a dict
        # ping the weather API and get the weather for each location
        # display the weather for each location on the map
        return None


if __name__ == '__main__':
    app.run(debug=False)
