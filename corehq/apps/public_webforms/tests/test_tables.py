from datetime import datetime
from unittest.mock import patch
from uuid import uuid4

import pytest
import pytz

from corehq.apps.public_webforms import tables
from corehq.apps.public_webforms.form_paths import FormPathSegment
from corehq.apps.public_webforms.models import (
    PublicWebform,
    PublicWebformStatus,
    PublicWebformType,
)
from corehq.apps.public_webforms.tables import PublicWebformTable

DOMAIN = 'public-webform-tables'
TIMEZONE = pytz.timezone('America/New_York')


def _table():
    return PublicWebformTable(data=[], domain=DOMAIN, timezone=TIMEZONE)


def _cells(webform):
    table = PublicWebformTable(data=[webform], domain=DOMAIN, timezone=TIMEZONE)
    [row] = table.rows
    return {column.name: str(value) for column, value in row.items()}


@pytest.mark.parametrize('status, expected_label', [
    (PublicWebformStatus.OPEN, "Open"),
    (PublicWebformStatus.CLOSED, "Closed"),
    (PublicWebformStatus.EXPIRED, "Expired"),
])
def test_every_status_renders_a_labelled_badge(status, expected_label):
    rendered = _table().render_status(status.value)

    assert expected_label in rendered
    assert 'badge' in rendered


@pytest.mark.parametrize('session_type, expected_label', [
    (PublicWebformType.REGISTRATION, "Registration"),
    (PublicWebformType.SURVEY, "Survey"),
])
def test_every_type_renders_a_labelled_badge(session_type, expected_label):
    rendered = _table().render_session_type(PublicWebform(session_type=session_type))

    assert expected_label in rendered
    assert 'badge' in rendered


@pytest.mark.parametrize('stored_utc, expected', [
    (datetime(2026, 9, 1, 21, 0), "Sep 01, 2026 17:00 EDT"),
    (datetime(2026, 12, 1, 22, 0), "Dec 01, 2026 17:00 EST"),
], ids=['daylight-saving-utc-4', 'standard-time-utc-5'])
def test_closing_time_is_shown_in_the_projects_timezone(stored_utc, expected):
    assert _table().render_expires_at(stored_utc) == expected


def _form_column(*path):
    webform = PublicWebform(id=1, label='Antenatal visit')
    with patch.object(
        tables, 'get_public_webform_form_paths', return_value={1: list(path)}
    ):
        return _cells(webform)['label']


def test_the_form_column_shows_the_label_over_a_linked_path():
    rendered = _form_column(
        FormPathSegment('Frontline Program', '/apps/view/app-1/', False),
        FormPathSegment('Registration', '/apps/view/app-1/module/menu-1/', False),
        FormPathSegment('Cohort Registration', '/apps/view/app-1/form/form-1/', False),
    )

    assert 'Antenatal visit' in rendered
    assert '/apps/view/app-1/module/menu-1/' in rendered
    assert 'Deleted' not in rendered


def test_the_form_column_marks_a_segment_that_has_left_the_app():
    """The webform still serves it, so the name stays — the link can't."""
    rendered = _form_column(
        FormPathSegment('Frontline Program', '/apps/view/app-1/', False),
        FormPathSegment('Registration', None, False),
        FormPathSegment('Cohort Registration', None, True),
    )

    assert 'Cohort Registration' in rendered
    assert 'Deleted' in rendered


def test_the_public_url_column_offers_the_url_to_copy():
    webform = PublicWebform(id=1, public_id=uuid4())

    rendered = _cells(webform)['public_url']

    assert webform.public_url in rendered
    assert 'clipboard' in rendered


@pytest.mark.parametrize('allow_email, allow_sms, expected_titles', [
    (True, False, ["Email enabled", "SMS disabled"]),
    (False, True, ["Email disabled", "SMS enabled"]),
    (True, True, ["Email enabled", "SMS enabled"]),
])
def test_delivery_marks_each_channel_as_on_or_off(
    allow_email, allow_sms, expected_titles
):
    webform = PublicWebform(allow_email=allow_email, allow_sms=allow_sms)

    rendered = _cells(webform)['delivery']

    for title in expected_titles:
        assert title in rendered
