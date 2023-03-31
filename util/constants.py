# General

API_NAME = 'Events API'
API_DESCRIPTION = 'Time-management and scheduling calendar service (Google Calendar) for Australians.'
DB_NAME = 'z5364199'
USAGE_MESSAGE = 'Usage: python3 z5364199.py georef-australia-state-suburb.csv au.csv'

# Schema

SCHEMA = (
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

# Error messages

INVALID_NAME_MSG = "{} is an invalid name. Please use a name with 1-64 characters"
INVALID_DATE_MSG = "{} is an invalid date format. Please use the YY-MM-DD format"
INVALID_TIME_MSG = "Invalid time format. Please use the HH:MM:SS format"
INVALID_TIME_RANGE_MSG = "Invalid time range"
INVALID_STREET_MSG = "{} is an invalid street. Please use a street with 1-64 characters"
INVALID_SUBURB_MSG = "{} is an invalid suburb. Please use a suburb with 1-64 characters"
INVALID_POSTCODE_MSG = "{} is not a valid Australian postcode"
INVALID_STATE_MSG = "{} is not a valid Australian state"
INVALID_DESCRIPTION_MSG = "{} is an invalid description. Please use a description with 1-64 characters"