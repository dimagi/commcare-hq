import datetime

import pytz
from time_machine import travel
from unmagic import use

from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone

from corehq.apps.public_webforms.tables import PublicWebformTable
from corehq.apps.public_webforms.tests.utils import (
    DOMAIN,
    NORMAL_USER,
    OTHER_DOMAIN,
    PublicWebformViewTestCase,
    create_session,
    create_webform,
)
from corehq.apps.public_webforms.views import PublicWebformTableView
from corehq.privileges import PUBLIC_WEBFORMS
from corehq.util.test_utils import flag_enabled, privilege_enabled


def _table_view(domain=DOMAIN, **params):
    view = PublicWebformTableView()
    view.args = (domain,)
    view.kwargs = {}
    view.request = RequestFactory().get('/', params)
    return view


@use('db')
def test_table_lists_only_webforms_on_domain():
    webform = create_webform()
    create_webform(domain='another-project')

    assert list(_table_view().get_queryset()) == [webform]


@use('db')
def test_table_lists_webforms_sorted_by_expiration():
    closing_soon = create_webform(expires_at=timezone.now() + datetime.timedelta(days=1))
    closing_later = create_webform(expires_at=timezone.now() + datetime.timedelta(days=90))
    closed = create_webform(expires_at=timezone.now() - datetime.timedelta(days=1))

    assert list(_table_view().get_queryset()) == [closing_later, closing_soon, closed]


@use('db')
def test_table_counts_webforms_submissions():
    webform = create_webform()
    create_session(webform, submitted_at=timezone.now())
    create_session(webform)

    [row] = _table_view().get_queryset()

    assert row.submissions == 1


@use('db')
@travel('2026-08-01')
def test_every_column_renders_from_the_queryset():
    """The columns are fed by annotations, so they break away from the table."""
    webform = create_webform(
        expires_at=datetime.datetime(2026, 9, 1, 21, 0), is_disabled=False)
    create_session(webform, submitted_at=timezone.now())
    table = PublicWebformTable(
        data=_table_view().get_queryset(), domain=DOMAIN, timezone=pytz.UTC)

    [row] = table.rows
    cells = {column.name: str(value) for column, value in row.items()}

    assert 'Antenatal visit' in cells['label']
    assert 'Survey' in cells['session_type']
    assert 'Open' in cells['status']
    assert cells['submissions'] == '1'
    assert cells['expires_at'] == 'Sep 01, 2026 21:00 UTC'
    assert 'fa-envelope' in cells['delivery']


@flag_enabled('PUBLIC_WEBFORMS')
@privilege_enabled(PUBLIC_WEBFORMS)
class TestPublicWebformQrCode(PublicWebformViewTestCase):

    def get(self, webform, domain=DOMAIN):
        url = reverse('public_webform_qr_code', args=[domain, webform.id])
        return self.client.get(url)

    def test_the_public_url_is_served_as_a_png(self):
        response = self.get(create_webform())

        assert response['Content-Type'] == 'image/png'

    def test_another_projects_webform_is_not_found(self):
        other = create_webform(domain=OTHER_DOMAIN)

        assert self.get(other).status_code == 404

    def test_a_qr_code_is_not_served_without_the_permission(self):
        webform = create_webform()
        self.sign_in(NORMAL_USER)

        assert self.get(webform).status_code != 200
