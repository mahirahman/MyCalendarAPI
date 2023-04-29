# MyCalendarAPI 🗓️

Time-management and scheduling calendar service API for Australians 📆

[![Made with Python](http://ForTheBadge.com/images/badges/made-with-python.svg)](https://www.python.org/)

## Getting Started

These instructions will get you a copy of the project up and running on your local machine for development and testing purposes. See below for prerequisite libraries and notes on how to deploy the project on a live system.

`git clone https://github.com/mahirahman/MyCalendarAPI.git`

To run the application locally:

1. CD to the directory of the project
2. Install the requirements by using the command `pip install -r requirements.txt`
3. Run `app.py`

### Interface

Endpoint | Description | Method | Data Type | Response
--- | --- | --- | --- | ---
`/events` | Create an event specified by the given payload | POST | **Payload:** `{ name, date, from, to, location: {street, suburb, state, post-code } description }` <br/> **Return Type:** `{ id, last-update, _links: { self: { href } } }` | **201:** Event Created Successfully <br/> **400:** Validation Error
`/events?order=<CSV-FORMATED-VALUE>&page=1&size=10&filter=<CSV-FORMATED-VALUE>` | Get all events | GET | **Parameters:**  `order, page, size, filter` <br/> **Return Type:** `{page, page-size, events: [ {id, name}, ... ], _links: { self: { href }, previous: { href } , next: { href } } }`| **200:** Successfully Retrieved All Events <br/> **400:** Validation Error <br/> **404:**	Events Not Found
`/events/{id}` | Get an event by its `ID` | GET | **Parameters:**  `id` <br/> **Return Type:** `{ id, last-update, name, date, from, to, location: {street, suburb, state, post-code } description, _metadata: { wind-speed, weather, humidity, temperature, holiday, weekend }, _links: { self: { href }, previous: { href } , next: { href } } } }` | **200:** Successfully Retrieved Event <br/> **404:** Event Not Found <br/> **500:** Error Getting Data From External API
`/events/{id}` | Update an event by its `ID` | PATCH |  **Parameters:**  `id` <br/> **Payload:** `{ name, date, from, to, location: {street, suburb, state, post-code } description,  }` <br/> **Return Type:** `{ id, last-update, _links: { self: { href } } }` | **200:** Event Updated Successfully <br/> **400:** Validation Error <br/> **404:** Event Was Not Found
`/events/{id}` | Delete an event by its `ID` | DELETE |  **Parameters:**  `id` <br/> **Return Type:** `{message, id}`  | **200:** Event Deleted Successfully <br/> **404:**	Event Was Not Found
`/events/statistics?format=<json/image>` | Get all event statistics | GET |  **Parameters:**  `format` <br/> **Return Type:** `json / image`  | **200:** Successfully Retrieved Event Statistics <br/> **400:** Validation Error <br/> **404:**	No Events Found
`/weather?date=2023-04-29` | Get the weather of popular Australian cities | GET |  **Parameters:**  `date` <br/> **Return Type:** `image`  | **200:** Successfully Retrieved Weather <br/> **400:** Validation Error <br/> **500:** Error Retrieving Weather Data

### Prerequisites

```
Python 3.7.x
Flask 1.1.2
flask_restx 1.1.0
geopandas 0.10.2
matplotlib 3.5.3
pandas 1.3.5
requests 2.25.1
shapely 2.0.1
```

## Notes

- Database is stored in the root directory of the project as `database.db`
- The API is for **personal** use only (individual) and is not intended for commercial use

## Built With

* [Python 3.7](https://www.python.org) - Programming Language
* [Flask RESTx](https://flask-restx.readthedocs.io/en) - API Library
* [Geopandas](https://geopandas.org/en) - Process Geographic Data
* [Matplotlib](https://matplotlib.org) - Visualization Library

## Versioning

We use [SemVer](http://semver.org/) for versioning.

## License

* [General Public License v2.0](https://github.com/mahirahman/Earth-Invaders/blob/master/LICENSE)

## Authors

* **Mahi Rahman**
