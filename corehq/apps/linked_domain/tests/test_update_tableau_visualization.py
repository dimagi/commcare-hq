from corehq.apps.reports.models import TableauVisualization, TableauServer
from corehq.apps.linked_domain.local_accessors import get_tableau_server_and_visualizations
from corehq.apps.linked_domain.tests.test_linked_apps import BaseLinkedAppsTest
from corehq.apps.linked_domain.updates import update_tableau_server_and_visualizations


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
        self.tableau_visualization_setup_1 = TableauVisualization(domain=self.domain,
        server=self.server, view_url='url_1')
        self.tableau_visualization_setup_1.save()

    def tearDown(self):
        self.server.delete()

    def test_update_tableau_server_and_visualizations(self):
        server_and_visualizations = get_tableau_server_and_visualizations(self.linked_domain)
        visualizations = server_and_visualizations["visualizations"]
        self.assertEqual(visualizations[0]['domain'], self.linked_domain)
        self.assertEqual(visualizations[0]['view_url'], '')

        # Update linked domain
        update_tableau_server_and_visualizations(self.domain_link)

        # Linked domain should now have master domain's tableau visualization
        models = TableauVisualization.objects.all().filter(domain=self.linked_domain).order_by('pk')

        self.assertEqual(models[0].view_url, 'url_1')
        self.assertEqual(models[0].server.server_name, 'server name')
        self.assertTrue(models[0].server.allow_domain_username_override)

        # Updating master reflected in linked domain after update
        self.tableau_visualization_setup_1.view_url = 'different url_1'
        self.tableau_visualization_setup_1.save()
        update_tableau_server_and_visualizations(self.domain_link)

        models = TableauVisualization.objects.all().filter(domain=self.linked_domain)
        self.assertEqual(models[0].view_url, 'different url_1')
