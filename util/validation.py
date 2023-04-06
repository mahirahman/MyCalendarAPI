from datetime import datetime
import util.constants as const
import re
from util.sql import execute_query

# Validate String


def string(str):
    return len(str) > 0 and len(str) <= 64

# Validate Date


def date(date_str):
    try:
        datetime.strptime(date_str, '%Y-%m-%d')
        return True
    except ValueError:
        return False

# Validate Time


def time(time_str):
    try:
        datetime.strptime(time_str, '%H:%M:%S')
        if len(time_str) == 8:
            return True
        else:
            return False
    except ValueError:
        return False

# Validate Time Range


def time_range(from_time_str, to_time_str):
    from_time = datetime.strptime(from_time_str, '%H:%M:%S')
    to_time = datetime.strptime(to_time_str, '%H:%M:%S')
    return from_time < to_time

# Validate Postcode


def postcode(postcode_str):
    return bool(re.match(r'^\d{4}$', postcode_str))

# Validate State


def state(state_str):
    return state_str.upper() in const.STATE_ABBREVIATIONS

# Validate all data fields in a request


def all_data(data):
    errors = {}
    if 'name' in data and not string(data['name']):
        errors['name'] = const.INVALID_NAME_MSG.format(data['name'])
    if 'date' in data and not date(data['date']):
        errors['date'] = const.INVALID_DATE_MSG.format(data['date'])
    if 'from' in data and 'to' in data and (
        not time(
            data['from']) or not time(
            data['to'])):
        errors['from'] = const.INVALID_TIME_MSG
    elif 'from' in data and 'to' in data and not time_range(data['from'], data['to']):
        errors['time_range'] = const.INVALID_TIME_RANGE_MSG
    if 'location' in data and 'street' in data['location'] and not string(
            data['location']['street']):
        errors['street'] = const.INVALID_STREET_MSG.format(
            data['location']['street'])
    if 'location' in data and 'suburb' in data['location'] and not string(
            data['location']['suburb']):
        errors['suburb'] = const.INVALID_SUBURB_MSG.format(
            data['location']['suburb'])
    if 'location' in data and 'post-code' in data['location'] and not postcode(
            data['location']['post-code']):
        errors['post-code'] = const.INVALID_POSTCODE_MSG.format(
            data['location']['post-code'])
    if 'location' in data and 'state' in data['location'] and not state(
            data['location']['state']):
        errors['state'] = const.INVALID_STATE_MSG.format(
            data['location']['state'])
    if 'description' in data and not string(data['description']):
        errors['description'] = const.INVALID_DESCRIPTION_MSG.format(
            data['description'])
    if not data:
        errors['data'] = 'No payload data provided'
    return errors

def is_event_overlap(params=()):
    return execute_query(
            "SELECT * FROM events WHERE date = ? AND time_from < ? AND time_to > ?",
            params)