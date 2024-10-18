#!/usr/bin/env python3

import datetime
import hashlib
import icalendar
import os
import pytz
import requests
import uuid

from bs4 import BeautifulSoup
from typing import List, Dict

CALENDAR_PAGE_URL = 'https://m.grundfoskoret.dk/korkalender'
USERNAME = os.environ.get('GRUNDFOSKORET_USERNAME')
PASSWORD = os.environ.get('GRUNDFOSKORET_PASSWORD')

TIMEZONE = pytz.timezone("Europe/Copenhagen")

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SRC_DIR)
DATA_DIR = os.path.join(ROOT_DIR, "data")
ICS_FILENAME = os.path.join(DATA_DIR, "grundfoskoret.ics")

MONTH_MAP = {
    'januar': 1,
    'februar': 2,
    'marts': 3,
    'april': 4,
    'maj': 5,
    'juni': 6,
    'juli': 7,
    'august': 8,
    'september': 9,
    'oktober': 10,
    'november': 11,
    'december': 12
}


def parse_date(date_text: str) -> Dict[str, any]:
    if " - " in date_text:
        return parse_double_date(date_text)
    else:
        return {
            **parse_single_date(date_text, 'start_'),
            **parse_single_date(date_text, 'end_'),
        }


def parse_double_date(date_text: str) -> Dict[str, any]:
    (start_text, end_text) = date_text.split(" - ")
    return {
        **parse_single_date(start_text, 'start_'),
        **parse_single_date(end_text, 'end_'),
    }


def parse_single_date(date_text: str, prefix: str = '') -> Dict[str, any]:
    date_text = date_text.partition("d. ")[2]
    (day_text, month_name, year_text) = date_text.split(" ")
    day = int(day_text.replace(".", ""))
    month = MONTH_MAP[month_name.lower()]
    year = int(year_text)

    return {prefix + 'day': day, prefix + 'month': month, prefix + 'year': year}


def parse_time(time_text: str) -> Dict[str, any]:
    (start_text, end_text) = time_text.split(" - ")
    (start_hour, start_min) = [int(x) for x in start_text.split(":")]
    (end_hour, end_min) = [int(x) for x in end_text.split(":")]

    return {'start_hour': start_hour, 'start_minute': start_min,
            'end_hour': end_hour, 'end_minute': end_min}


def parse_events(html: str) -> List[Dict[str, any]]:
    soup = BeautifulSoup(html, 'html.parser')

    result = []
    for elem in soup.select('.calendar-event-title'):
        if len(elem.contents) < 3:
            continue

        title = elem.contents[0]
        if not title:
            continue

        date_text = elem.contents[1].contents[0]
        if not date_text:
            continue

        date_data = parse_date(date_text)
        if date_data['start_year'] < 2023:
            continue

        time_text = elem.contents[2].contents[0]
        if not time_text:
            continue

        time_data = parse_time(time_text)

        start_datetime = TIMEZONE.localize(datetime.datetime(
            year=date_data['start_year'],
            month=date_data['start_month'],
            day=date_data['start_day'],
            hour=time_data['start_hour'],
            minute=time_data['start_minute']
        ))

        end_datetime = TIMEZONE.localize(datetime.datetime(
            year=date_data['end_year'],
            month=date_data['end_month'],
            day=date_data['end_day'],
            hour=time_data['end_hour'],
            minute=time_data['end_minute']
        ))

        if title and date_text and time_text:
            result.append({
                'title': title,
                'start': start_datetime,
                'end': end_datetime,
                'cancelled': "aflyst" in title.lower()
            })

    return result


def get_uuid(dt: datetime, counter_map: Dict[str, int]) -> str:
    date_part = dt.date().isoformat()

    counter = counter_map.get(date_part, 0)
    counter = counter + 1
    counter_map[date_part] = counter

    unique_value = '%s:%d' % (date_part, counter)

    hexvalue = hashlib.md5(unique_value.encode('utf-8')).hexdigest()

    return uuid.UUID(hexvalue)


def get_vtimezone() -> icalendar.cal.Timezone:
    tz = icalendar.cal.Timezone()
    tz.add('tzid', 'Europe/Copenhagen')
    daylight = icalendar.cal.TimezoneDaylight()
    daylight.add('tzname', 'CEST')
    daylight.add('tzoffsetfrom', datetime.timedelta(hours=1))
    daylight.add('tzoffsetto', datetime.timedelta(hours=2))
    daylight.add('dtstart', datetime.datetime.fromtimestamp(0))
    daylight.add('rrule', {'freq': 'YEARLY', 'bymonth': 3, 'byday': '-1SU'})
    tz.add_component(daylight)
    standard = icalendar.cal.TimezoneStandard()
    standard.add('tzname', 'CET')
    standard.add('tzoffsetfrom', datetime.timedelta(hours=2))
    standard.add('tzoffsetto', datetime.timedelta(hours=1))
    standard.add('dtstart', datetime.datetime.fromtimestamp(0))
    standard.add('rrule', {'freq': 'YEARLY', 'bymonth': 10, 'byday': '-1SU'})
    tz.add_component(standard)

    return tz


def eventdata_to_calendar(eventdata_list: List[Dict[str, any]]) -> icalendar.Calendar:
    calendar = icalendar.Calendar()

    calendar.add('prodid', '-//grundfoskoret-calendar//grundfoskoret.dk//')
    calendar.add('version', '2.0')
    calendar.add_component(get_vtimezone())

    now = TIMEZONE.localize(datetime.datetime.now())

    event_counters = {}

    for eventdata in eventdata_list:
        event = icalendar.Event()

        start_date = eventdata['start']

        event.add('uid', get_uuid(start_date, event_counters))
        event.add('dtstamp', now)
        event.add('name', eventdata['title'])
        event.add('description', eventdata['title'])
        event.add('dtstart', start_date)
        event.add('dtend', eventdata['end'])

        if eventdata['cancelled']:
            event.add('method', 'CANCEL')
            event.add('status', 'CANCELLED')

        calendar.add_component(event)

    return calendar


def write_calendar_to_file(calendar: icalendar.Calendar) -> None:
    with open(ICS_FILENAME, 'wb') as f:
        f.write(calendar.to_ical())


def main() -> None:

    response = requests.post(CALENDAR_PAGE_URL, data={
        "frontend_login_username": USERNAME,
        "frontend_login_password": PASSWORD
    })

    eventdata = parse_events(response.text)
    calendar = eventdata_to_calendar(eventdata)
    write_calendar_to_file(calendar)


if __name__ == '__main__':
    main()
