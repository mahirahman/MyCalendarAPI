import pandas as pd
import json
import sqlite3
from datetime import datetime
from flask import Flask, request
from flask_restx import Resource, Api, fields

app = Flask(__name__)
api = Api(app)

connection = sqlite3.connect('z5364199.db', check_same_thread=False)
with connection:
    cursor = connection.cursor()
    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS events(
                       event_id INTEGER PRIMARY KEY,
                       name TEXT,
                       date DATE,
                       time_from TIME,
                       time_to TIME,
                       street TEXT,
                       suburb TEXT,
                       state TEXT,
                       post_code TEXT,
                       description TEXT
                   )
                   """)
    connection.commit()

# Schema of an event
eventModel = api.model('Event', {
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
    @api.expect(eventModel, validate=False)
    def post(self):
        eventBody = request.json
        isOverlap = pd.read_sql_query("""SELECT * FROM events WHERE date = ? AND time_from < ? AND time_to > ?""",
                                      connection, params=(eventBody['date'], eventBody['to'], eventBody['from'],))

        if not isOverlap.empty:
            return {"Error": "Event overlaps with another event", "Overlap": isOverlap.to_json()}, 400

        eventId = pd.read_sql_query(
            "SELECT COUNT(*) FROM events", connection).iloc[0, 0] + 1
        with connection:
            cursor = connection.cursor()
            cursor.execute("""
                           INSERT INTO events VALUES(NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                           """, (eventBody['name'], eventBody['date'], eventBody['from'], eventBody['to'],
                                 eventBody['location']['street'], eventBody['location']['suburb'], eventBody['location']['state'],
                                 eventBody['location']['post-code'], eventBody['description']))
            connection.commit()
        return {'id': int(eventId), 'last-update': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), '_links': {'self': {'href': f'/events/{str(eventId)}'}}}, 201


if __name__ == '__main__':
    app.run(debug=False)
