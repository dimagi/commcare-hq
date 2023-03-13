from django.urls import reverse

from testil import assert_raises

from corehq import privileges
from corehq.motech.dhis2.tests.test_views import BaseViewTest
from corehq.motech.models import ConnectionSettings
from corehq.motech.repeaters.models import FormRepeater
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
