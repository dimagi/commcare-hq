from types import SimpleNamespace

from django.test import SimpleTestCase
from django.urls import reverse

from corehq.apps.dashboard.models import Tile


class TileQuickActionTests(SimpleTestCase):

    def _make_request(self, can_access_all_locations=True):
        return SimpleNamespace(
            domain='test-domain',
            can_access_all_locations=can_access_all_locations,
        )

    def _make_tile(self, request, **kwargs):
        return Tile(
            request,
            title='Applications',
            slug='applications',
            icon='fcc fcc-flower',
            **kwargs,
        )

    def test_no_quick_action_configured_returns_none(self):
        request = self._make_request()
        tile = self._make_tile(request)
        assert tile.get_quick_action_url(request) is None

    def test_quick_action_url_for_unrestricted_user(self):
        request = self._make_request()
        tile = self._make_tile(
            request,
            quick_action_icon='fa fa-plus',
            quick_action_urlname='default_new_app',
            quick_action_label='New Application',
        )
        expected = reverse('default_new_app', args=[request.domain])
        assert tile.get_quick_action_url(request) == expected

    def test_quick_action_hidden_when_visibility_check_fails(self):
        request = self._make_request()
        tile = self._make_tile(
            request,
            quick_action_urlname='default_new_app',
            quick_action_visibility_check=lambda req: False,
        )
        assert tile.get_quick_action_url(request) is None

    def test_quick_action_hidden_for_location_restricted_user(self):
        # default_new_app is not location safe, so users who cannot access
        # all locations should not be offered the quick action
        request = self._make_request(can_access_all_locations=False)
        tile = self._make_tile(
            request,
            quick_action_urlname='default_new_app',
        )
        assert tile.get_quick_action_url(request) is None
