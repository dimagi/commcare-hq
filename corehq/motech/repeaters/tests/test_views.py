from django.urls import reverse

from testil import assert_raises

from corehq import privileges
from corehq.motech.dhis2.tests.test_views import BaseViewTest
from corehq.motech.models import ConnectionSettings
from corehq.motech.repeaters.models import SQLFormRepeater
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
        cls.repeater = SQLFormRepeater.objects.create(
            domain=cls.domain.name,
            connection_settings=conn,
        )
        cls.url_kwargs = {
            'domain': cls.domain.name,
            'repeater_id': cls.repeater.repeater_id
        }

    @privilege_enabled(privileges.DATA_FORWARDING)
    def test_drop_repeater(self):
        response = self.client.post(reverse('drop_repeater', kwargs=self.url_kwargs))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f'/a/{self.domain.name}/motech/forwarding/')
        with assert_raises(SQLFormRepeater.DoesNotExist):
            SQLFormRepeater.objects.get(id=self.repeater.id)
