from datetime import timezone, timedelta
import time
from util.sql import execute_query

def convert_to_utc(dt):
    # Get the local timezone as a string (e.g. 'PST', 'EST', 'CET', etc.)
    local_timezone = time.tzname[time.localtime().tm_isdst]

    # Get the offset from UTC time in seconds
    utc_offset_secs = -time.timezone if time.localtime().tm_isdst == 0 else - \
        time.altzone

    # Create a timezone object with the offset from UTC time in seconds
    tz = timezone(timedelta(seconds=utc_offset_secs), local_timezone)

    return dt.astimezone(timezone.utc)

def get_total_events():
    return execute_query("SELECT COUNT(*) FROM events")[0][0]

def get_datetime_in_format(dt_obj, format="%Y-%m-%d %H:%M:%S"):
    return dt_obj.strftime(format)
