#!/usr/bin/env python3

import datetime
import os
import pytz
import requests

from bs4 import BeautifulSoup

CALENDAR_PAGE_URL = 'https://m.grundfoskoret.dk/korkalender'
USERNAME = os.environ.get('GRUNDFOSKORET_USERNAME')
PASSWORD = os.environ.get('GRUNDFOSKORET_PASSWORD')

TIMEZONE = pytz.timezone("Europe/Copenhagen")

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


def parse_date(date_text):
    if " - " in date_text:
        return parse_double_date(date_text)
    else:
        return {
            **parse_single_date(date_text, 'start_'),
            **parse_single_date(date_text, 'end_'),
        }


def parse_double_date(date_text):
    (start_text, end_text) = date_text.split(" - ")
    return {
        **parse_single_date(start_text, 'start_'),
        **parse_single_date(end_text, 'end_'),
    }


def parse_single_date(date_text, prefix=''):
    date_text = date_text.partition("d. ")[2]
    (day_text, month_name, year_text) = date_text.split(" ")
    day = int(day_text.replace(".", ""))
    month = MONTH_MAP[month_name.lower()]
    year = int(year_text)

    return {prefix + 'day': day, prefix + 'month': month, prefix + 'year': year}


def parse_time(time_text):
    (start_text, end_text) = time_text.split(" - ")
    (start_hour, start_min) = [int(x) for x in start_text.split(":")]
    (end_hour, end_min) = [int(x) for x in end_text.split(":")]

    return {'start_hour': start_hour, 'start_minute': start_min,
            'end_hour': end_hour, 'end_minute': end_min}


def parse_events(html):
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
                'start': start_datetime.isoformat(),
                'end': end_datetime.isoformat(),
                'cancelled': "aflyst" in title.lower()
            })

    return result


def main():
    response = requests.post(CALENDAR_PAGE_URL, data={
        "frontend_login_username": USERNAME,
        "frontend_login_password": PASSWORD
    })

    print(parse_events(response.text))


if __name__ == '__main__':
    main()
