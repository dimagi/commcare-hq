import datetime

from unmagic import use

from django.test import RequestFactory
from django.utils import timezone

from corehq.apps.public_webforms.tests.utils import DOMAIN, create_webform
from corehq.apps.public_webforms.views import PublicWebformTableView


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
