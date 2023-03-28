import pandas as pd
import json
import sqlite3
from flask import Flask, request
from flask_restx import Resource, Api, fields

app = Flask(__name__)
api = Api(app)
connection = sqlite3.connect('z5364199.db')
cursor = connection.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS events(
        event_id INTEGER PRIMARY KEY,
        name TEXT,
        date TEXT,
        time_from TEXT,
        time_to TEXT,
        street TEXT,
        suburb TEXT,
        state TEXT,
        post_code INTEGER,
        description TEXT
    )
""")

# populate db with sample data
cursor.execute("""INSERT INTO events VALUES(1, "Birthday Party", "01-01-2000", "16:00", "20:00", "215B Night Av", "Kensington", "NSW", 2033, "The cake is a lie")""")
# populate db with sample data
cursor.execute("""INSERT INTO events VALUES(2, "Birthday Party 123", "01-01-2000", "16:00", "20:00", "215B Night Av", "Kensington", "NSW", 2033, "The cake is a lie")""")

# Schema of an event
eventModel = api.model('Event', {
    "name": fields.String(example="Birthday Party"),
    "date": fields.Date(example="01-01-2000"),
    "from": fields.String(example="16:00"),
    "to": fields.String(example="20:00"),
    "location": fields.Nested(api.model('Location', {
        'street': fields.String(example="215B Night Av"),
        'suburb': fields.String(example="Kensington"),
        'state': fields.String(example="NSW"),
        'post-code': fields.Integer(example="2033")
    })),
    "description": fields.String(example="The cake is a lie")
})


@api.route('/events')
class Event(Resource):

    @api.response(201, 'Event Created Successfully')
    @api.response(400, 'Validation Error')
    @api.doc(description="Create a new event")
    @api.expect(eventModel, validate=False)
    def post(self):
        eventBody = request.json

        # Your API should not allow adding a new event, or modifying an event if it has overlapping time with other events. For instance, one event can finish at 16:00 on the same day that another starts at 16:00, it cannot start at 15:45.
        # if db is not empty and event overlaps with another event
        if (cursor.execute("""SELECT * FROM events""").fetchone() is not None and cursor.execute("""SELECT * FROM events WHERE date=? AND time_from<? AND time_to>?""", (eventBody['date'], eventBody['from'], eventBody['to'])).fetchone() is not None):
            return {"Error": "Event overlaps with another event"}, 400

        # event is valid, get total number of records + 1 for eventID, add to db
        cursor.execute("""SELECT COUNT(*) FROM events""")
        eventID = cursor.fetchone()[0] + 1
        cursor.execute("""INSERT INTO events VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (eventID, eventBody['name'], eventBody['date'], eventBody['from'], eventBody[
                       'to'], eventBody['location']['street'], eventBody['location']['suburb'], eventBody['location']['state'], eventBody['location']['post-code'], eventBody['description']))

        # 201 Created
        # {
        #     "id" : 123,
        #     "last-update": "2023-04-08 12:34:40",
        #     "_links": {
        #         "self": {
        #           "href": "/events/123"
        #         }
        #     }
        # }
        return {'id': 123, 'last-update': 'time when record created', '_links': {'self': {'href': '/events/123'}}}, 201


if __name__ == '__main__':
    app.run(debug=True)
