from datetime import datetime, timedelta, date
from calendar import monthrange
import math
import re
from io import BytesIO
from collections import defaultdict
import pandas as pd
import geopandas as gpd
import matplotlib
import matplotlib.pyplot as plt
import requests
from flask import Flask, request, Response
from flask_restx import Api, Resource, fields, reqparse
from shapely.geometry import Point
import util.validation as validation
import util.constants as const
from util.sql import execute_query
import util.helper as util

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

    @api.response(201, 'Event Created Successfully')
    @api.response(400, 'Validation Error')
    @api.doc(description="Create an event specified by the given payload")
    @api.expect(event_model, validate=True)
    def post(self):
        '''Create an event specified by the given payload'''
        request_data = request.json

        # Check request data contains all required fields
        if not const.FIELDS.issubset(
            request_data.keys()) or not const.LOCATION_FIELDS.issubset(request_data.get('location',{}).keys()):
            return {"Error": "Missing required fields"}, 400

        # Validate request data
        validation_errors = validation.all_data(request_data)
        if validation_errors:
            return {"Errors": validation_errors}, 400

        # Check if event overlaps with another event
        if validation.is_event_overlap((request_data['date'],
                                        request_data['to'],
                                        request_data['from'])):
            return {"Error": "Event overlaps with another event"}, 400
        curr_time = util.get_datetime_in_format(datetime.now())
        event_id = util.get_total_events() + 1
        execute_query(
            "INSERT INTO events VALUES(NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (request_data['name'],
             request_data['date'],
             request_data['from'],
             request_data['to'],
             request_data['location']['street'],
             request_data['location']['suburb'],
             request_data['location']['state'],
             request_data['location']['post-code'],
             request_data['description'],
             curr_time))

        return {'id': int(event_id), 'last-update': curr_time,
                '_links': {'self': {'href': f'/events/{str(event_id)}'}}}, 201

    order_parser = reqparse.RequestParser()
    order_parser.add_argument(
        'order',
        type=str,
        help="Sort order - comma-separated value to sort the list based on the given criteria.\
        The string consists of two parts: the first part is a special character `+` or `-` where\
        `+` indicates ordering ascendingly, and `-` indicates ordering descendingly. The second\
        part is an attribute name which is one of **{id, name, datetime}**",
        default='+id')
    order_parser.add_argument('page', type=int, help='Page number', default=1)
    order_parser.add_argument('size', type=int, help='Page size', default=10)
    order_parser.add_argument(
        'filter',
        type=str,
        help='Fields to include in response - comma-separated value (combination of: **id, name,\
            date, from, to, and location**), and shows what attribute should be shown for each\
            event accordingly.',
        default='id,name')

    @api.response(200, 'Successfully Retrieved All Events')
    @api.response(400, 'Validation Error')
    @api.response(404, 'Events Not Found')
    @api.doc(description="Get all events")
    @api.expect(order_parser)
    def get(self):
        '''Get all events'''
        args = self.order_parser.parse_args()
        arg_order = args['order']
        arg_page = args['page']
        arg_size = args['size']
        arg_filter = args['filter']

        # Validate arg_order
        # Translation table that removes characters with ASCII codes 43 (+) and 45 (-)
        field_names = [name.translate({43: None, 45: None})
                       for name in arg_order.split(',')]
        if not re.match(
                const.ORDER_PATTERN,
                arg_order) or not const.ORDER_FIELDS.issuperset(field_names):
            return {"Error": "Invalid order query"}, 400

        # Validate arg_page
        if arg_page < 1:
            return {"Error": "Invalid page query"}, 400

        # Validate arg_size
        if arg_size < 1:
            return {"Error": "Invalid size query"}, 400

        # Validate arg_filter
        if not re.match(
                const.FILTER_PATTERN,
                arg_filter) or not const.FILTER_FIELDS.issuperset(
                arg_filter.split(',')):
            return {"Error": "Invalid filter query"}, 400

        # If the filter query contains location, from or to then replace them
        # with their corresponding attribute names
        arg_filter = [
            v if v not in {
                'location',
                'from',
                'to'} else {
                'location': 'street,suburb,state,post_code',
                'from': 'time_from',
                'to': 'time_to'}[v] for v in arg_filter.split(',')]
        arg_filter = ','.join(arg_filter)

        # Construct order string
        order_criteria = []
        date_criteria = []
        for order in arg_order.split(','):
            order_type, attr_name = order[0], order[1:]
            if attr_name == 'datetime':
                date_criteria.append(
                    f"date {const.ORDER_DIRECTION[order_type]}, time_from {const.ORDER_DIRECTION[order_type]}")
            else:
                order_criteria.append(
                    f"{attr_name} {const.ORDER_DIRECTION[order_type]}")
        order_string = ', '.join(date_criteria + order_criteria)

        result = execute_query(
            f"SELECT {arg_filter} FROM 'events'\
            ORDER BY {order_string}\
            LIMIT {arg_size}\
            OFFSET {(arg_page - 1) * arg_size}"
        )
        if not result:
            return {"Error": f"No events found on page {arg_page}"}, 404

        # Construct links
        links = {
            "self": {
                "href": f"/events?order={arg_order}&page={arg_page}&size={arg_size}&filter={arg_filter}",
            },
        }
        num_pages = math.ceil(util.get_total_events() / arg_size)
        if arg_page < num_pages:
            links["next"] = {
                "href": f"/events?order={arg_order}&page={arg_page + 1}&size={arg_size}&filter={arg_filter}",
            }

        # Construct events
        events = []
        for row in result:
            event = {}
            for i, field in enumerate(arg_filter.split(',')):
                if field == 'time_from':
                    event['time'] = row[i]
                elif field == 'time_to':
                    event['to'] = row[i]
                elif field in {'street', 'suburb', 'state', 'post_code'}:
                    event.setdefault(
                        'location', {})[
                        field.replace(
                            '_', '-')] = row[i]
                else:
                    event[field] = row[i]
            events.append(event)

        return {
            "page": arg_page,
            "page-size": arg_size,
            "events": events,
            "_links": links,
        }, 200


@api.route('/events/<int:id>')
@api.param('id', 'The event identifier')
class Events(Resource):

    @api.response(200, 'Successfully Retrieved Event')
    @api.response(404, 'Event Not Found')
    @api.response(500, 'Error Getting Data From External API')
    @api.doc(description="Get an event by its ``ID``")
    def get(self, id):
        '''Get an event by its ID'''
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
        geo_df = pd.read_csv("au_geo.csv", delimiter=';')
        geo_df = geo_df.drop(
            columns=[
                'Geo Shape',
                'Year',
                'Official Code State',
                'Official Code Local Government Area',
                'Official Name Local Government Area',
                'Official Code Suburb',
                'Iso 3166-3 Area Code',
                'Type'])
        df = geo_df[['Geo Point', 'Official Name Suburb',
                        'Official Name State']].dropna()
        rows = df[df['Official Name Suburb'].str.contains(
            event[6]) & df['Official Name State'].str.contains(const.STATE_ABBREVIATIONS[event[7].upper()])]

        # Check if there exists a suburb with the same name in the same state
        if not rows.empty:
            # Get the first row from row dataframe
            row = rows.iloc[0]
            lat, lng = row['Geo Point'].split(',')[0].replace(' ', ''), row['Geo Point'].split(',')[1].replace(' ', '')
            url = f"https://www.7timer.info/bin/civil.php?lon={lng}&lat={lat}&lang=en&ac=0&unit=metric&output=json"
            response = requests.get(url)
            if response.status_code == 200:
                init_date_obj = datetime.strptime(response.json().get('init'), '%Y%m%d%H')
                event_date_obj = datetime.strptime(event[2], '%Y-%m-%d').date()
                from_time_obj = datetime.strptime(event[3], '%H:%M:%S').time()

                event_datetime_obj = datetime.combine(
                    event_date_obj, from_time_obj)
                event_datetime_utc_str = str(
                    util.convert_to_utc(event_datetime_obj))
                event_datetime_utc_str_without_tz = event_datetime_utc_str[:-6]
                event_datetime_utc_obj = datetime.strptime(
                    event_datetime_utc_str_without_tz, '%Y-%m-%d %H:%M:%S')

                # Check if date and from_time is within a valid range
                start_time = init_date_obj + timedelta(hours=3)
                end_time = init_date_obj + timedelta(hours=195)
                if (event_datetime_utc_obj >= start_time) and (
                        event_datetime_utc_obj < end_time):
                    dataseries = response.json().get('dataseries')
                    hours_between = (
                        event_datetime_utc_obj - init_date_obj).total_seconds() // 3600
                    # Calculate the number of dataseries elements that fall within the time period
                    count = sum(1 for d in response.json().get(
                        'dataseries') if 0 <= d.get('timepoint') <= hours_between) - 1
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
                return {"Error": "Error getting weather data from 7timer"}, 500

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
    @api.doc(description="Delete an event by its ``ID``")
    def delete(self, id):
        '''Delete an event by its ID'''
        event = execute_query("SELECT * FROM events WHERE id = ?", (id,))
        if not event:
            return {"Error": f"Event {id} doesn't exist"}, 404

        execute_query("DELETE FROM events WHERE id = ?", (id,))
        return {
            "message": f"The event with id {id} has been removed", "id": id}, 200

    @api.response(404, 'Event Was Not Found')
    @api.response(200, 'Event Updated Successfully')
    @api.response(400, 'Validation Error')
    @api.doc(description="Update an event by its ``ID``")
    @api.expect(event_model, validate=True)
    def patch(self, id):
        '''Update an event by its ID'''
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
        is_overlap = validation.is_event_overlap((
            request_data['date'] if 'date' in data_keys else execute_query(
                "SELECT date FROM events WHERE id = ?", (id,))[0][0],
            request_data['to'] if 'to' in data_keys else execute_query(
                "SELECT time_to FROM events WHERE id = ?", (id,))[0][0],
            request_data['from'] if 'from' in data_keys else execute_query(
                "SELECT time_from FROM events WHERE id = ?", (id,))[0][0],
        ))
        if is_overlap and is_overlap[0][0] != id:
            return {"Error": "Event overlaps with another event"}, 400

        # Update event in database
        curr_time = util.get_datetime_in_format(datetime.now())
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
        help='Format of the statistics, can be either "json" or "image"',
        default='json'
    )

    @api.expect(statistics_parser)
    @api.response(200, 'Successfully Retrieved Event Statistics')
    @api.response(400, 'Validation Error')
    @api.response(404, 'No Events Found')
    @api.doc(description="Get all event statistics")
    def get(self):
        '''Get all event statistics'''
        # Validate it is either json or image format
        args = self.statistics_parser.parse_args()
        if args['format'] not in ['json', 'image']:
            return {"Error": "Invalid format provided"}, 400

        # Total Number of events
        total_events = util.get_total_events()
        if total_events == 0:
            return {"Error": "No events found"}, 404
        # Total Number of events in current calendar Week (Today to Sunday)
        today = date.today()
        next_sunday = today + timedelta(days=(6 - today.weekday()) % 7)
        total_events_current_week = execute_query(
            "SELECT COUNT(*) FROM events WHERE date BETWEEN ? AND ?",
            (util.get_datetime_in_format(datetime.now(), '%Y-%m-%d'), next_sunday))[0][0]

        # Total Number of events in current calendar month
        first_day = today.replace(day=1)
        last_day = today.replace(day=28) + timedelta(days=4)

        # Count the number of events in the current month
        total_events_current_month = execute_query(
            "SELECT COUNT(*) FROM events WHERE date BETWEEN ? AND ?",
            (
                util.get_datetime_in_format(first_day, '%Y-%m-%d'),
                util.get_datetime_in_format(last_day, '%Y-%m-%d')
            ))[0][0]

        # Number of events per day
        min_max_dates = execute_query(
            "SELECT MIN(date), MAX(date) FROM events")
        start_date = datetime.strptime(min_max_dates[0][0], '%Y-%m-%d').date()
        end_date = datetime.strptime(min_max_dates[0][1], '%Y-%m-%d').date()
        query_result = execute_query(
            "SELECT date FROM events WHERE date BETWEEN ? AND ?", (start_date, end_date))
        events_per_day = defaultdict(int)
        for row in query_result:
            event_date = datetime.strptime(row[0], '%Y-%m-%d').date()
            events_per_day[util.get_datetime_in_format(
                event_date, '%d-%m-%Y')] += 1

        if args['format'] == 'json':
            return {
                "total": total_events,
                "total-current-week": total_events_current_week,
                "total-current-month": total_events_current_month,
                "per-days": dict(events_per_day)
            }, 200
        else:
            # Get the number of events per month of the current year
            current_year = datetime.now().year
            events_per_month = {}
            for month in range(1, 13):
                first_day = date(current_year, month, 1)
                last_day = date(current_year, month, monthrange(current_year, month)[1])
                total_events_current_month = execute_query(
                    "SELECT COUNT(*) FROM events WHERE date BETWEEN ? AND ?",
                    (util.get_datetime_in_format(
                        first_day,
                        '%Y-%m-%d'),
                        util.get_datetime_in_format(
                        last_day,
                        '%Y-%m-%d')))[0][0]
                events_per_month[util.get_datetime_in_format(
                    first_day, '%b')] = total_events_current_month

            # Plot the graph
            fig, ax = plt.subplots()
            ax.bar(events_per_month.keys(), events_per_month.values())
            ax.set_xlabel('Month')
            ax.set_ylabel('Number of Events')
            ax.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
            ax.set_title(f'Events per Month in Current Year ({current_year})')
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
        help='Date in the format ``YYYY-MM-DD``',
        default=util.get_datetime_in_format(datetime.now(), '%Y-%m-%d'),
    )

    @api.expect(date_parser)
    @api.response(200, 'Successfully Retrieved Weather')
    @api.response(400, 'Validation Error')
    @api.response(500, 'Error Retrieving Weather Data')
    @api.doc(description="Get the weather of popular Australian cities")
    def get(self):
        '''Get the weather of popular Australian cities'''
        # Validate the date is in the correct format
        args = self.date_parser.parse_args()
        if not validation.date(args['date']):
            return {"Error": "Invalid date format provided"}, 400
        # Validate the date is within a week
        date_diff = (datetime.strptime(args['date'], '%Y-%m-%d').date() - date.today()).days
        if date_diff > 7 or date_diff < 0:
            return {"Error": "Date is not within a week"}, 400

        # Read the CSV file containing location data
        au_df = pd.read_csv("au_location.csv")
        au_df = au_df.drop(['country',
                            'iso2',
                            'admin_name',
                            'capital',
                            'population',
                            'population_proper'],
                           axis=1)

        # Filter the data to include only the first occurrence of each popular location
        au_df = au_df[au_df['city'].isin(const.POPULAR_LOCATIONS)].groupby('city').first().reset_index()

        # Get the weather data for each location
        for loc in const.POPULAR_LOCATIONS:
            row = au_df[au_df['city'] == loc].iloc[0]
            url = f"https://www.7timer.info/bin/civil.php?lon={row['lng']}&lat={row['lat']}&lang=en&ac=0&unit=metric&output=json"
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                row_index = au_df[au_df['city'] == loc].index[0]
                # Get first element if date is today
                if date_diff == 0:
                    au_df.at[row_index, 'temperature'] = data.get('dataseries')[0].get('temp2m')
                else:
                    # Otherwise get 4th element of the day (midday)
                    init_date_obj = datetime.strptime(data.get('init'), '%Y%m%d%H')
                    event_date_obj = datetime.strptime(args['date'], '%Y-%m-%d').date()
                    event_date_obj = datetime.combine(event_date_obj, datetime.min.time())
                    event_datetime_utc_str = str(util.convert_to_utc(event_date_obj))
                    event_datetime_utc_obj = datetime.strptime(event_datetime_utc_str[:-6], '%Y-%m-%d %H:%M:%S')

                    # Calculate the number of 3-hour intervals between init_date_obj and event_datetime_utc_obj
                    num_intervals = (event_datetime_utc_obj - init_date_obj).total_seconds() // (3 * 60 * 60)
                    # If the number of intervals is negative, set temperature to None
                    if num_intervals < 0:
                        temperature = None
                        return {"Error": "Error retrieving weather data"}, 500
                    else:
                        # Get the temperature for the corresponding interval
                        temperature = data.get('dataseries')[int(num_intervals)].get('temp2m')
                    # Update the temperature value in the dataframe
                    au_df.at[row_index, 'temperature'] = temperature
            else:
                return {"Error": "Error retrieving weather data"}, 500
        # Create a GeoDataFrame with the Point objects as the geometry column
        geometry = [Point(xy) for xy in zip(au_df['lng'], au_df['lat'])]
        gdf = gpd.GeoDataFrame(au_df, geometry=geometry)

        matplotlib.use('Agg')
        # Plot the image
        img = plt.imread('util/au_map.jpg')
        fig, ax = plt.subplots(figsize=(10, 10))
        ax.imshow(img, extent=[112.90, 153.70, -43.70, -10.50])

        # Add annotation boxes to the points
        for _, row in gdf.iterrows():
            xytext = (-60, 5) if row['city'] == 'Brisbane' else (-30, 5)
            text = f"{row['city']} {int(row['temperature'])}°C"
            ax.annotate(
                text,
                xy=row['geometry'].coords[0],
                xytext=xytext,
                textcoords="offset points",
                bbox=dict(
                    facecolor='white',
                    edgecolor='black'),
                fontsize=8)

        # Remove x and y axis
        ax.set_xticks([])
        ax.set_yticks([])
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['bottom'].set_visible(False)
        ax.spines['left'].set_visible(False)

        # Hide the red dot plots
        gdf.plot(ax=ax, alpha=0)

        # Show the plot
        buffer = BytesIO()
        plt.savefig(buffer, format='png', bbox_inches='tight')
        buffer.seek(0)

        return Response(buffer.getvalue(), mimetype='image/png')


if __name__ == '__main__':
    app.run(debug=False)
