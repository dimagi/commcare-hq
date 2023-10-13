from datetime import timedelta, date

from nose.tools import assert_equal

from ..forms import EventForm
from ..models import Event

DOMAIN = 'test-domain'


def test_field_availability_no_event():
    avail = EventForm.determine_field_availability(None)
    assert_equal(avail, {
        'attendance_target': 1,
        'end_date': 1,
        'expected_attendees': 1,
        'location_id': 1,
        'name': 1,
        'sameday_reg': 1,
        'start_date': 1,
        'tracking_option': 1,
    })


def test_field_availability_event_not_started():
    tomorrow = date.today() + timedelta(days=1)
    event = get_event(tomorrow)
    avail = EventForm.determine_field_availability(event)
    assert_equal(avail, {
        'attendance_target': 1,
        'end_date': 1,
        'expected_attendees': 1,
        'location_id': 1,
        'name': 1,
        'sameday_reg': 1,
        'start_date': 1,
        'tracking_option': 1,
    })


def test_field_availability_event_in_progress_no_attendance():
    event = get_event(date.today())
    avail = EventForm.determine_field_availability(event)
    assert_equal(avail, {
        'attendance_target': 1,
        'end_date': 1,
        'expected_attendees': 1,
        'location_id': 1,
        'name': 0,
        'sameday_reg': 1,
        'start_date': 0,
        'tracking_option': 1,
    })


def test_field_availability_event_in_progress_with_attendance():
    event = get_event(date.today(), attendance=5)
    avail = EventForm.determine_field_availability(event)
    assert_equal(avail, {
        'attendance_target': 0,
        'end_date': 1,
        'expected_attendees': 0,
        'location_id': 0,
        'name': 0,
        'sameday_reg': 1,
        'start_date': 0,
        'tracking_option': 0,
    })


def test_field_availability_event_completed():
    yesterday = date.today() - timedelta(days=1)
    event = get_event(yesterday, attendance=5)
    avail = EventForm.determine_field_availability(event)
    assert_equal(avail, {
        'attendance_target': 0,
        'end_date': 0,
        'expected_attendees': 0,
        'location_id': 0,
        'name': 0,
        'sameday_reg': 0,
        'start_date': 0,
        'tracking_option': 0,
    })


def get_event(on_date, attendance=0):
    event = Event(
        name='test event',
        domain=DOMAIN,
        start_date=on_date,
        end_date=on_date,
        attendance_target=5,
        total_attendance=attendance,
        manager_id='c0ffee'
    )
    return event
