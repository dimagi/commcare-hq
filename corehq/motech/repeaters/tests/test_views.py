from django.urls import reverse

from testil import assert_raises

from corehq import privileges
from corehq.apps.domain.shortcuts import create_domain
from corehq.motech.dhis2.tests.test_views import BaseViewTest
from corehq.motech.models import ConnectionSettings
from corehq.motech.repeaters.models import FormRepeater, ShortFormRepeater
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

    @privilege_enabled(privileges.DATA_FORWARDING)
    def test_cannot_claim_repeater_from_another_domain_via_post(self):
        victim_domain = create_domain('victim-domain')
        self.addCleanup(victim_domain.delete)
        victim_conn = ConnectionSettings.objects.create(
            domain=victim_domain.name,
            name='victim_conn',
            url='https://example.com/api/',
        )
        victim_repeater = ShortFormRepeater.objects.create(
            domain=victim_domain.name,
            connection_settings=victim_conn,
        )
        url = reverse('edit_repeater', kwargs={
            'domain': self.domain.name,  # Attacker's domain
            'repeater_type': victim_repeater.repeater_type,
            'repeater_id': victim_repeater.repeater_id,
        })
        post_data = {
            'request_method': 'POST',
            # Attacker's ConnectionSettings instance
            'connection_settings_id': self.connection_setting.id,
        }

        self.client.raise_request_exception = False  # The POST raises a 500
        self.client.post(url, post_data)

        # Verify that the repeater remains untouched
        victim_repeater.refresh_from_db()
        assert victim_repeater.domain == victim_domain.name
        assert victim_repeater.connection_settings_id == victim_conn.id
