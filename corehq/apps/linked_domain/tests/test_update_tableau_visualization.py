from corehq.apps.reports.models import TableauVisualization, TableauServer
from corehq.apps.linked_domain.local_accessors import get_tableau_visualizaton
from corehq.apps.linked_domain.tests.test_linked_apps import BaseLinkedAppsTest
from corehq.apps.linked_domain.updates import update_tableau_visualization


class TestUpdateTableauVisualization(BaseLinkedAppsTest):
    def setUp(self):
        server = TableauServer(domain=self.domain,
        server_type='server',
        server_name='server name',
        validate_hostname='host name',
        target_site='target site',
        domain_username='username',
        allow_domain_username_override=True)
        self.tableau_visualization_setup = TableauVisualization(domain=self.domain, server=server, view_url='url')

    def tearDown(self):
        self.tableau_visualization_setup.delete()

    def test_update_tableau_visualization(self):
        self.assertEqual({'domain': self.linked_domain, 'view_url': '', },
        get_tableau_visualizaton(self.linked_domain))

        # Update linked domain
        update_tableau_visualization(self.domain_link)

        # Linked domain should now have master domain's tableau visualization
        model = TableauVisualization.objects.get(domain=self.linked_domain)

        self.assertEqual(model.view_url, 'url')
        self.assertEqual(model.server.server_name, 'server name')
        self.assertTrue(model.server.allow_domain_username_override)

        # Updating master reflected in linked domain after update
        self.tableau_visualization_setup.view_url = 'different url'
        self.tableau_visualization_setup.server.server_name = 'different server name'
        self.tableau_visualization_setup.save()
        update_tableau_visualization(self.domain_link)

        model = TableauVisualization.objects.get(domain=self.linked_domain)
        self.assertEqual(model.view_url, 'different url')
        self.assertEqual(model.server.server_name, 'different server name')
