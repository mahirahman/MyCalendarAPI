# General
API_NAME = 'Events API'
API_DESCRIPTION = 'Time-management and scheduling calendar service (Google Calendar) for Australians.'
DB_NAME = 'z5364199'
USAGE_MESSAGE = 'Usage: python3 z5364199.py georef-australia-state-suburb.csv au.csv'

# Schema
SCHEMA = (
    """
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY,
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

FIELDS = {'name', 'date', 'from', 'to', 'location', 'description'}
ORDER_FIELDS = {'id', 'name', 'datetime'}
FILTER_FIELDS = {'id', 'name', 'date', 'from', 'to', 'location'}
LOCATION_FIELDS = {'street', 'suburb', 'state', 'post-code'}

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

# Location Data
STATE_ABBREVIATIONS = {
    'NSW': 'New South Wales',
    'VIC': 'Victoria',
    'QLD': 'Queensland',
    'SA': 'South Australia',
    'WA': 'Western Australia',
    'TAS': 'Tasmania',
    'NT': 'Northern Territory',
    'ACT': 'Australian Capital Territory'
}

POPULAR_LOCATIONS = ['Sydney', 'Canberra', 'Melbourne', 'Brisbane', 'Perth', 'Adelaide', 'Hobart', 'Darwin', 'Broome', 'Alice Springs', 'Cairns']

# Weather Data
CLOUD_COVER = {
    1: '0%-6%',
    2: '6%-19%',
    3: '19%-31%',
    4: '31%-44%',
    5: '44%-56%',
    6: '56%-69%',
    7: '69%-81%',
    8: '81%-94%',
    9: '94%-100%'
}

PRECEPICTION_TYPE = {
    'snow': 'Snow',
    'rain': 'Rain',
    'frzr': 'Freezing rain',
    'icep': 'Ice pellets',
    'none': 'None',
}

PRECEPICTION_RATE = {
    0: 'None',
    1: '0-0.25mm/hr',
    2: '0.25-1mm/hr',
    3: '1-4mm/hr',
    4: '4-10mm/hr',
    5: '10-16mm/hr',
    6: '16-30mm/hr',
    7: '30-50mm/hr',
    8: '50-75mm/hr',
    9: 'Over 75mm/hr',
}

WEATHER_SPEED = {
    1: "Below 1.08 km/h (Calm)",
    2: "1.08-12.24 km/h (Light)",
    3: "12.24-28.8 km/h (Moderate)",
    4: "28.8-38.88 km/h (Fresh)",
    5: "38.88-61.92 km/h (Strong)",
    6: "61.92-88.2 km/h (Gale)",
    7: "88.2-117.36 km/h (Storm)",
    8: "Over 117.36 km/h (Hurricane)"
}

WEATHER_CONDITION = {
    "clearday": "Total cloud cover less than 20%",
    "clearnight": "Total cloud cover less than 20%",
    "pcloudyday": "Total cloud cover between 20%-60%",
    "pcloudynight": "Total cloud cover between 20%-60%",
    "mcloudyday": "Total cloud cover between 60%-80%",
    "mcloudynight": "Total cloud cover between 60%-80%",
    "cloudyday": "Total cloud cover over over 80%",
    "cloudynight": "Total cloud cover over over 80%",
    "humidday": "Relative humidity over 90% with total cloud cover less than 60%",
    "humidnight": "Relative humidity over 90% with total cloud cover less than 60%",
    "lightrainday": "Precipitation rate less than 4mm/hr with total cloud cover more than 80%",
    "lightrainnight": "Precipitation rate less than 4mm/hr with total cloud cover more than 80%",
    "oshowerday": "Precipitation rate less than 4mm/hr with total cloud cover between 60%-80%",
    "oshowernight": "Precipitation rate less than 4mm/hr with total cloud cover between 60%-80%",
    "ishowerday": "Precipitation rate less than 4mm/hr with total cloud cover less than 60%",
    "ishowernight": "Precipitation rate less than 4mm/hr with total cloud cover less than 60%",
    "lightsnowday": "Precipitation rate less than 4mm/hr",
    "lightsnownight": "Precipitation rate less than 4mm/hr",
    "rainday": "Precipitation rate over 4mm/hr",
    "rainnight": "Precipitation rate over 4mm/hr",
    "snowday": "Precipitation rate over 4mm/hr",
    "snownight": "Precipitation rate over 4mm/hr",
    "rainsnowday": "Precipitation type to be ice pellets or freezing rain",
    "rainsnownight": "Precipitation type to be ice pellets or freezing rain",
    "tsday": "Lifted Index less than -5 with precipitation rate below 4mm/hr",
    "tsnight": "Lifted Index less than -5 with precipitation rate below 4mm/hr",
    "tsrainday": "Lifted Index less than -5 with precipitation rate over 4mm/hr",
    "tsrainnight": "Lifted Index less than -5 with precipitation rate over 4mm/hr"
}
