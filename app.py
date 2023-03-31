import sys
import pandas as pd
from datetime import datetime
from flask import Flask, request
import requests
from flask_restx import Api, Resource, fields
from util.sql import execute_query
import util.validation as validation
import util.constants as const

if len(sys.argv) != 3:
    print(const.USAGE_MESSAGE)
    sys.exit(1)

app = Flask(__name__)
api = Api(app,
          default=const.API_NAME,
          title=const.API_NAME,
          description=const.API_DESCRIPTION,)

au_df = pd.read_csv(sys.argv[2])
georef_df = pd.read_csv(sys.argv[1], delimiter=';')

execute_query(const.SCHEMA)

# Schema of an event
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
    @api.doc(description="Create a new event")
    @api.expect(event_model, validate=True)
    def post(self):
        request_data = request.json

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
        insert_params = (request_data['name'], request_data['date'], request_data['from'], request_data['to'],
                         request_data['location']['street'], request_data['location']['suburb'], request_data['location']['state'],
                         request_data['location']['post-code'], request_data['description'], curr_time)
        execute_query(insert_query, insert_params)
        return {'id': int(event_id), 'last-update': curr_time, '_links': {'self': {'href': f'/events/{str(event_id)}'}}}, 201


@api.route('/events/<int:id>')
@api.param('id', 'The Event identifier')
class Events(Resource):

    @api.response(200, 'Successfully retrieved event')
    @api.response(404, 'Event not found')
    @api.response(502, 'Error getting holiday data from NagerDate')
    @api.doc(description="Get all books")
    def get(self, id):
        event = execute_query(
            "SELECT * FROM events WHERE event_id = ?", (id,))[0]
        if not event:
            return {"Error": f"Event {id} doesn't exist"}, 404

        previous_event = execute_query(
            "SELECT * FROM events WHERE date < ? OR (date = ? AND time_to < ?) ORDER BY date DESC, time_to DESC LIMIT 1", (event[2], event[2], event[3]))
        next_event = execute_query(
            "SELECT * FROM events WHERE date > ? OR (date = ? AND time_from > ?) ORDER BY date ASC, time_from ASC LIMIT 1", (event[2], event[2], event[4]))

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
            return {"Error": "Error getting holiday data from NagerDate"}, 502

        # Get weather data
        # lng	[deg, float] WGS84 coordinates of the site.
        # lat	[deg, float] WGS84 coordinates of the site.
        # https://www.7timer.info/bin/civil.php?lat=-33.865143&lng=151.209900&ac=1&unit=metric&output=json&product=two
            # "_metadata": {
            #     "wind-speed": "data[wind10m['speed']] KM",
            #     "weather": "data['weather']",
            #     "humidity": "data['rh2m']",
            #     "temperature": "data['temp2m'] °C",
            # },
        # if the date is within the next 7 days then get the weather data

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


if __name__ == '__main__':
    app.run(debug=False)
