import datetime

import pytz
from time_machine import travel
from unmagic import use

from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from corehq.apps.public_webforms.models import (
    PublicFormSession,
    PublicWebformStatus,
)
from corehq.apps.public_webforms.tables import PublicWebformTable
from corehq.apps.public_webforms.tests.mixins import (
    NORMAL_USER,
    PublicWebformViewTestMixin,
)
from corehq.apps.public_webforms.tests.utils import (
    DOMAIN,
    OTHER_DOMAIN,
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


def _create_session(webform, **kwargs):
    return PublicFormSession.objects.create(
        public_webform=webform,
        expires_at=timezone.now() + datetime.timedelta(days=1),
        **kwargs,
    )


@use('db')
def test_the_table_lists_only_the_projects_own_webforms():
    webform = create_webform()
    create_webform(domain='another-project')

    assert list(_table_view().get_queryset()) == [webform]


@use('db')
def test_the_table_lists_the_webforms_with_the_most_life_left_first():
    closing_soon = create_webform(expires_at=timezone.now() + datetime.timedelta(days=1))
    closing_later = create_webform(expires_at=timezone.now() + datetime.timedelta(days=90))
    closed = create_webform(expires_at=timezone.now() - datetime.timedelta(days=1))

    assert list(_table_view().get_queryset()) == [closing_later, closing_soon, closed]


@use('db')
def test_the_table_counts_webforms_submissions():
    webform = create_webform()
    _create_session(webform, submitted_at=timezone.now())
    _create_session(webform)

    [row] = _table_view().get_queryset()

    assert row.submissions == 1


@use('db')
def test_the_table_rows_carry_the_status_the_status_column_renders():
    create_webform(is_disabled=True)

    [row] = _table_view().get_queryset()

    assert row.status == PublicWebformStatus.CLOSED


@use('db')
@travel('2026-08-01')
def test_every_column_renders_from_the_queryset():
    """The columns are fed by annotations, so they break away from the table."""
    webform = create_webform(
        expires_at=datetime.datetime(2026, 9, 1, 21, 0), is_disabled=False)
    _create_session(webform, submitted_at=timezone.now())
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
class TestPublicWebformQrCode(PublicWebformViewTestMixin, TestCase):

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
