from datetime import datetime
from flask import Flask, request
from flask_restx import Api, Resource, fields
from util.sql import execute_query

app = Flask(__name__)
api = Api(app,
          default="Events",
          title="Events API",
          description="Time-management and scheduling calendar service (Google Calendar) for Australians.")  # Documentation Description)

execute_query(
    """
        CREATE TABLE IF NOT EXISTS events (
            event_id INTEGER PRIMARY KEY,
            name TEXT,
            date DATE,
            time_from TIME,
            time_to TIME,
            street TEXT,
            suburb TEXT,
            state TEXT,
            post_code TEXT,
            description TEXT,
            last_update DATETIME
        )
    """)

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
class Event(Resource):

    @api.response(201, 'Event Created Successfully')
    @api.response(400, 'Validation Error')
    @api.doc(description="Create a new event")
    @api.expect(event_model, validate=True)
    def post(self):
        request_data = request.json
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


if __name__ == '__main__':
    app.run(debug=False)
