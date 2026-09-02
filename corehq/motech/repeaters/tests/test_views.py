import pytest
from django.urls import reverse

from testil import assert_raises

from corehq import privileges
from corehq.motech.dhis2.tests.test_views import BaseViewTest
from corehq.motech.models import ConnectionSettings
from corehq.motech.repeaters.const import State
from corehq.motech.repeaters.models import FormRepeater, RepeatRecord
from corehq.motech.repeaters.views.repeat_records import DomainForwardingRepeatRecords
from corehq.util.test_utils import privilege_enabled


class TestRepeaterViews(BaseViewTest):

    @classmethod
    def _create_data(cls):
        conn = ConnectionSettings(
            domain=cls.domain.name,
            name="motech_conn",
            url="url",
        )
        conn.save()
        cls.connection_setting = conn

    @privilege_enabled(privileges.DATA_FORWARDING)
    def test_drop_repeater(self):
        repeater = FormRepeater.objects.create(
            domain=self.domain.name,
            connection_settings=self.connection_setting,
        )
        url_kwargs = {
            'domain': self.domain.name,
            'repeater_id': repeater.repeater_id
        }
        response = self.client.post(reverse('drop_repeater', kwargs=url_kwargs))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f'/a/{self.domain.name}/motech/forwarding/')
        with assert_raises(FormRepeater.DoesNotExist):
            FormRepeater.objects.get(id=repeater.id)

    @privilege_enabled(privileges.DATA_FORWARDING)
    def test_pause_repeater(self):
        repeater = FormRepeater.objects.create(
            domain=self.domain.name,
            connection_settings=self.connection_setting,
        )
        url_kwargs = {
            'domain': self.domain.name,
            'repeater_id': repeater.repeater_id
        }
        response = self.client.post(reverse('pause_repeater', kwargs=url_kwargs))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f'/a/{self.domain.name}/motech/forwarding/')
        self.assertEqual(FormRepeater.objects.get(id=repeater.id).is_paused, True)

    @privilege_enabled(privileges.DATA_FORWARDING)
    def test_resume_repeater(self):
        repeater = FormRepeater.objects.create(
            domain=self.domain.name,
            connection_settings=self.connection_setting,
            is_paused=True
        )
        url_kwargs = {
            'domain': self.domain.name,
            'repeater_id': repeater.repeater_id
        }
        response = self.client.post(reverse('resume_repeater', kwargs=url_kwargs))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f'/a/{self.domain.name}/motech/forwarding/')
        self.assertEqual(FormRepeater.objects.get(id=repeater.id).is_paused, False)

    @privilege_enabled(privileges.DATA_FORWARDING)
    def test_no_access_to_repeater_from_outside_domain(self):
        repeater = FormRepeater.objects.create(
            domain='other-domain',
            connection_settings=self.connection_setting,
        )
        url_kwargs = {
            'domain': self.domain.name,
            'repeater_type': repeater.repeater_type,
            'repeater_id': repeater.repeater_id
        }
        response = self.client.get(reverse('edit_repeater', kwargs=url_kwargs))
        assert response.status_code == 404


def _render_payload_button(state):
    record = RepeatRecord(domain='test', state=state)
    # The method uses no instance state, so call it unbound with a dummy self.
    return DomainForwardingRepeatRecords._make_view_payload_button(None, record)


@pytest.mark.parametrize('state', [State.Success, State.Empty])
def test_payload_button_disabled_for_succeeded_records(state):
    assert 'disabled' in _render_payload_button(state)


@pytest.mark.parametrize('state', [State.Pending, State.Fail, State.Cancelled])
def test_payload_button_active_for_non_succeeded_records(state):
    assert 'disabled' not in _render_payload_button(state)
