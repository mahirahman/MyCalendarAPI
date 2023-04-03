from datetime import timezone, timedelta
import time


def convert_to_utc(dt):
    # get the local timezone as a string (e.g. 'PST', 'EST', 'CET', etc.)
    local_timezone = time.tzname[time.localtime().tm_isdst]

    # get the offset from UTC time in seconds
    utc_offset_secs = -time.timezone if time.localtime().tm_isdst == 0 else - \
        time.altzone

    # create a timezone object with the offset from UTC time in seconds
    tz = timezone(timedelta(seconds=utc_offset_secs), local_timezone)

    return dt.astimezone(timezone.utc)
