from django.test import SimpleTestCase
from django.urls import reverse

from corehq.apps.dashboard.models import Tile


class _StubRequest(object):

    def __init__(self, can_access_all_locations=True):
        self.domain = 'test-domain'
        self.can_access_all_locations = can_access_all_locations


def _make_tile(request, **kwargs):
    return Tile(
        request,
        title='Applications',
        slug='applications',
        icon='fcc fcc-flower',
        **kwargs,
    )


class TileQuickActionTests(SimpleTestCase):

    def test_no_quick_action_configured_returns_none(self):
        request = _StubRequest()
        tile = _make_tile(request)
        self.assertIsNone(tile.get_quick_action_url(request))

    def test_quick_action_url_for_unrestricted_user(self):
        request = _StubRequest()
        tile = _make_tile(
            request,
            quick_action_icon='fa fa-plus',
            quick_action_urlname='default_new_app',
            quick_action_label='New Application',
        )
        self.assertEqual(
            tile.get_quick_action_url(request),
            reverse('default_new_app', args=[request.domain]),
        )

    def test_quick_action_hidden_when_visibility_check_fails(self):
        request = _StubRequest()
        tile = _make_tile(
            request,
            quick_action_urlname='default_new_app',
            quick_action_visibility_check=lambda req: False,
        )
        self.assertIsNone(tile.get_quick_action_url(request))

    def test_quick_action_hidden_for_location_restricted_user(self):
        # default_new_app is not location safe, so users who cannot access
        # all locations should not be offered the quick action
        request = _StubRequest(can_access_all_locations=False)
        tile = _make_tile(
            request,
            quick_action_urlname='default_new_app',
        )
        self.assertIsNone(tile.get_quick_action_url(request))
