import pytest
from django.test import Client
from django.urls import reverse

from corehq.apps.domain.models import Domain
from corehq.apps.users.models import WebUser
from corehq.apps.campdash.models import CampaignDashboard


@pytest.fixture(scope="module")
def domain_setup():
    domain_name = 'test-domain'
    domain = Domain.get_or_create_with_name(domain_name)
    username = 'test@example.com'
    password = 'testpassword'
    user = WebUser.create(domain_name, username, password, None, None)
    user.is_superuser = True
    user.save()
    
    yield domain_name, domain, username, password, user
    
    user.delete(domain_name, deleted_by=None)
    domain.delete()


@pytest.fixture
def dashboard(db, domain_setup):
    domain_name = domain_setup[0]
    dashboard = CampaignDashboard.objects.create(
        domain=domain_name,
        name='Test Dashboard',
        description='Test dashboard description',
        created_by=domain_setup[2],  # username
        is_active=True
    )
    return dashboard


@pytest.fixture
def authenticated_client(domain_setup):
    client = Client()
    username, password = domain_setup[2], domain_setup[3]
    client.login(username=username, password=password)
    return client


class TestCampaignDashboardView:
    """Test cases for the CampaignDashboardView"""

    def test_dashboard_view_accessible(self, authenticated_client, domain_setup, dashboard):
        """Test that the dashboard view is accessible"""
        domain_name = domain_setup[0]
        url = reverse('campaign_dashboard', args=[domain_name])
        response = authenticated_client.get(url)
        
        assert response.status_code == 200
        assert 'campdash/dashboard.html' in [t.name for t in response.templates]
        assert 'Campaign Dashboard' in response.content.decode('utf-8')

    def test_dashboard_view_context(self, authenticated_client, domain_setup, dashboard):
        """Test that the dashboard view context contains the expected data"""
        domain_name = domain_setup[0]
        url = reverse('campaign_dashboard', args=[domain_name])
        response = authenticated_client.get(url)
        
        assert response.status_code == 200
        
        # Check that the context contains the expected data
        assert 'gauges' in response.context
        assert 'report' in response.context
        assert 'map_data' in response.context
        assert response.context['domain'] == domain_name
        
        # Check that there are 3 gauges
        assert len(response.context['gauges']) == 3
        
        # Check that the report has the expected structure
        assert 'title' in response.context['report']
        assert 'headers' in response.context['report']
        assert 'rows' in response.context['report']
        
        # Check that the map data has the expected structure
        assert 'title' in response.context['map_data']
        assert 'type' in response.context['map_data']
        assert 'center' in response.context['map_data']
        assert 'zoom' in response.context['map_data']


class TestCampaignDashboardSettingsView:
    """Test cases for the CampaignDashboardSettingsView"""

    def test_settings_view_accessible(self, authenticated_client, domain_setup, dashboard):
        """Test that the settings view is accessible"""
        domain_name = domain_setup[0]
        url = reverse('campaign_dashboard_settings', args=[domain_name])
        response = authenticated_client.get(url)
        
        assert response.status_code == 200
        assert 'campdash/settings.html' in [t.name for t in response.templates]
        assert 'Campaign Dashboard Settings' in response.content.decode('utf-8')

    def test_settings_view_context(self, authenticated_client, domain_setup, dashboard):
        """Test that the settings view context contains the expected data"""
        domain_name = domain_setup[0]
        url = reverse('campaign_dashboard_settings', args=[domain_name])
        response = authenticated_client.get(url)
        
        assert response.status_code == 200
        
        # Check that the context contains the expected data
        assert 'dashboards' in response.context
        assert response.context['domain'] == domain_name
        
        # Check that the dashboards queryset contains our test dashboard
        assert len(response.context['dashboards']) == 1
        assert response.context['dashboards'][0].name == 'Test Dashboard'


class TestCampaignDashboardData:
    """Test cases for the campaign_dashboard_data view"""

    def test_dashboard_data_endpoint(self, authenticated_client, domain_setup, dashboard):
        """Test that the dashboard data endpoint returns the expected data"""
        domain_name = domain_setup[0]
        url = reverse('campaign_dashboard_data', args=[domain_name])
        response = authenticated_client.get(url)
        
        assert response.status_code == 200
        
        # Check that the response is JSON
        assert response['Content-Type'] == 'application/json'
        
        # Check that the response contains the expected data
        data = response.json()
        assert 'gauges' in data
        assert 'report' in data
        assert 'map' in data
        
        # Check that there are 3 gauges
        assert len(data['gauges']) == 3
        
        # Check that the report has the expected structure
        assert 'title' in data['report']
        assert 'headers' in data['report']
        assert 'rows' in data['report']
        
        # Check that the map has the expected structure
        assert 'title' in data['map']
        assert 'type' in data['map']
        assert 'center' in data['map']
        assert 'zoom' in data['map']
        assert 'markers' in data['map']
        
        # Check that there are markers in the map data
        assert len(data['map']['markers']) > 0 