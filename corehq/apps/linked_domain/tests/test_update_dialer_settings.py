from corehq.apps.integration.models import DialerSettings

from corehq.apps.linked_domain.local_accessors import get_dialer_settings
from corehq.apps.linked_domain.tests.test_linked_apps import BaseLinkedDomainTest
from corehq.apps.linked_domain.updates import update_dialer_settings


class TestUpdateDialerSettings(BaseLinkedDomainTest):
    def setUp(self):
        self.dialer_setup = DialerSettings(domain=self.domain,
                                           aws_instance_id='id_314159',
                                           is_enabled=True,
                                           dialer_page_header='header',
                                           dialer_page_subheader='subheader')
        self.dialer_setup.save()

    def tearDown(self):
        self.dialer_setup.delete()

    def test_update_dialer_settings(self):
        self.assertEqual({'domain': self.linked_domain,
                          'aws_instance_id': '',
                          'dialer_page_header': '',
                          'dialer_page_subheader': '',
                          'is_enabled': False}, get_dialer_settings(self.linked_domain))

        # Initial update of linked domain
        update_dialer_settings(self.domain_link)

        # Linked domain should now have master domain's dialer settings
        model = DialerSettings.objects.get(domain=self.linked_domain)

        self.assertEqual(model.aws_instance_id, 'id_314159')
        self.assertTrue(model.is_enabled)
        self.assertEqual(model.dialer_page_header, 'header')
        self.assertEqual(model.dialer_page_subheader, 'subheader')

        # Updating master reflected in linked domain after update
        self.dialer_setup.aws_instance_id = 'id_000000'
        self.dialer_setup.save()
        update_dialer_settings(self.domain_link)

        model = DialerSettings.objects.get(domain=self.linked_domain)
        self.assertEqual(model.aws_instance_id, 'id_000000')
