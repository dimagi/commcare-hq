from corehq.apps.reports.models import TableauServer
from corehq.apps.linked_domain.local_accessors import get_tableau_server_and_visualizations
from corehq.apps.linked_domain.tests.test_linked_apps import BaseLinkedAppsTest
from corehq.apps.linked_domain.updates import update_tableau_server_and_visualizations


class TestUpdateTableauServer(BaseLinkedAppsTest):
    def setUp(self):
        self.tableau_server_setup = TableauServer(domain=self.domain,
        server_type='server',
        server_name='server name',
        validate_hostname='host name',
        target_site='target site',
        domain_username='username')
        self.tableau_server_setup.save()

    def tearDown(self):
        self.tableau_server_setup.delete()

    def test_update_tableau_server(self):
        server_and_visualizations = get_tableau_server_and_visualizations(self.linked_domain)
        server = server_and_visualizations["server"]
        self.assertEqual({'domain': self.linked_domain,
        'server_name': '',
        'domain_username': '',
        'server_type': 'server',
        'target_site': 'Default',
        'validate_hostname': '', },
        server)

        # Update linked domain
        update_tableau_server_and_visualizations(self.domain_link)

        # Linked domain should now have master domain's tableau server
        model = TableauServer.objects.get(domain=self.linked_domain)

        self.assertEqual(model.target_site, 'target site')
        self.assertEqual(model.server_name, 'server name')

        # Updating master reflected in linked domain after update
        self.tableau_server_setup.target_site = 'different target site'
        self.tableau_server_setup.server_name = 'different server name'
        self.tableau_server_setup.save()
        update_tableau_server_and_visualizations(self.domain_link)

        model = TableauServer.objects.get(domain=self.linked_domain)
        self.assertEqual(model.target_site, 'different target site')
        self.assertEqual(model.server_name, 'different server name')
