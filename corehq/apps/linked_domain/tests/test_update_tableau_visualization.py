from corehq.apps.reports.models import TableauVisualization, TableauServer
from corehq.apps.linked_domain.local_accessors import get_tableau_visualizaton
from corehq.apps.linked_domain.tests.test_linked_apps import BaseLinkedAppsTest
from corehq.apps.linked_domain.updates import update_tableau_visualization


class TestUpdateTableauVisualization(BaseLinkedAppsTest):
    def setUp(self):
        self.server = TableauServer(domain=self.domain,
        server_type='server',
        server_name='server name',
        validate_hostname='host name',
        target_site='target site',
        domain_username='username',
        allow_domain_username_override=True)
        self.server.save()
        self.tableau_visualization_setup = TableauVisualization(domain=self.domain,
        server=self.server, view_url='url')
        self.tableau_visualization_setup.save()

    def tearDown(self):
        self.server.delete()

    def test_update_tableau_visualization(self):
        visualization = get_tableau_visualizaton(self.linked_domain)
        self.assertEqual(visualization['domain'], self.linked_domain)
        self.assertEqual(visualization['view_url'], '')

        # Update linked domain
        update_tableau_visualization(self.domain_link)

        # Linked domain should now have master domain's tableau visualization
        model = TableauVisualization.objects.get(domain=self.linked_domain)

        self.assertEqual(model.view_url, 'url')
        self.assertEqual(model.server.server_name, 'server name')
        self.assertTrue(model.server.allow_domain_username_override)

        # Updating master reflected in linked domain after update
        self.tableau_visualization_setup.view_url = 'different url'
        self.tableau_visualization_setup.save()
        update_tableau_visualization(self.domain_link)

        model = TableauVisualization.objects.get(domain=self.linked_domain)
        self.assertEqual(model.view_url, 'different url')
