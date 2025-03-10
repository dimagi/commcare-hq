from io import StringIO
import json

import pytest
from django.test import TestCase

from corehq.apps.domain.models import Domain
from corehq.apps.domain.deletion import apply_deletion_operations
from corehq.apps.dump_reload.sql.dump import get_objects_to_dump
from corehq.apps.campdash.models import (
    CampaignDashboard,
    DashboardGauge,
    DashboardReport,
    DashboardMap,
)


@pytest.fixture
def domain_with_dashboard(db):
    # Create domain
    domain_name = 'test-domain'
    domain = Domain.get_or_create_with_name(domain_name)
    
    # Create a dashboard for the domain
    dashboard = CampaignDashboard.objects.create(
        domain=domain_name,
        name='Test Dashboard',
        description='Test dashboard description',
        created_by='test-user',
        is_active=True
    )
    
    # Create related objects
    gauge = DashboardGauge.objects.create(
        dashboard=dashboard,
        title='Test Gauge',
        gauge_type='progress',
        min_value=0,
        max_value=100,
        current_value=50,
        display_order=1
    )
    
    report = DashboardReport.objects.create(
        dashboard=dashboard,
        title='Test Report',
        report_type='table',
        config={
            'headers': ['Region', 'Target', 'Completed', 'Progress'],
            'rows': [
                ['North', 500, 350, '70%'],
                ['South', 600, 390, '65%'],
            ]
        },
        display_order=1
    )
    
    map_obj = DashboardMap.objects.create(
        dashboard=dashboard,
        title='Test Map',
        map_type='markers',
        config={
            'center': [0, 0],
            'zoom': 2,
            'markers': [
                {'lat': 40.7128, 'lng': -74.0060, 'label': 'New York', 'value': 350},
                {'lat': 34.0522, 'lng': -118.2437, 'label': 'Los Angeles', 'value': 290},
            ]
        },
        display_order=1
    )
    
    yield domain_name, domain, dashboard, gauge, report, map_obj
    
    # Cleanup
    try:
        domain.delete()
    except:
        pass


@pytest.fixture
def other_domain_with_dashboard(db):
    # Create another domain
    other_domain_name = 'other-domain'
    other_domain = Domain.get_or_create_with_name(other_domain_name)
    
    # Create a dashboard for the other domain
    other_dashboard = CampaignDashboard.objects.create(
        domain=other_domain_name,
        name='Other Dashboard',
        description='Other dashboard description',
        created_by='test-user',
        is_active=True
    )
    
    yield other_domain_name, other_domain, other_dashboard
    
    # Cleanup
    other_domain.delete()


class TestDomainDeletion:
    """Test that Campaign Dashboard models are properly deleted when a domain is deleted"""

    def test_domain_deletion_deletes_dashboard(self, domain_with_dashboard, other_domain_with_dashboard):
        """Test that deleting a domain deletes its dashboards"""
        domain_name, _, dashboard, _, _, _ = domain_with_dashboard
        other_domain_name, _, _ = other_domain_with_dashboard
        
        # Verify that the dashboard exists
        assert CampaignDashboard.objects.filter(domain=domain_name).exists()
        assert DashboardGauge.objects.filter(dashboard=dashboard).exists()
        assert DashboardReport.objects.filter(dashboard=dashboard).exists()
        assert DashboardMap.objects.filter(dashboard=dashboard).exists()
        
        # Delete the domain
        apply_deletion_operations(domain_name)
        
        # Verify that the dashboard and related objects are deleted
        assert not CampaignDashboard.objects.filter(domain=domain_name).exists()
        assert not DashboardGauge.objects.filter(dashboard=dashboard).exists()
        assert not DashboardReport.objects.filter(dashboard=dashboard).exists()
        assert not DashboardMap.objects.filter(dashboard=dashboard).exists()
        
        # Verify that the other domain's dashboard still exists
        assert CampaignDashboard.objects.filter(domain=other_domain_name).exists()


class TestDomainDump:
    """Test that Campaign Dashboard models are properly included in domain dumps"""

    def test_domain_dump_includes_dashboard(self, domain_with_dashboard):
        """Test that dumping a domain includes its dashboards"""
        domain_name, _, dashboard, gauge, report, map_obj = domain_with_dashboard
        
        # Get objects to dump
        objects = list(get_objects_to_dump(domain_name, [], []))
        
        # Convert objects to JSON for easier inspection
        output = StringIO()
        for obj in objects:
            output.write(obj + '\n')
        
        output_str = output.getvalue()
        
        # Check that the dashboard and related objects are included in the dump
        assert '"model": "campdash.campaigndashboard"' in output_str
        assert '"model": "campdash.dashboardgauge"' in output_str
        assert '"model": "campdash.dashboardreport"' in output_str
        assert '"model": "campdash.dashboardmap"' in output_str
        
        # Check that the dashboard data is correct
        assert dashboard.name in output_str
        assert gauge.title in output_str
        assert report.title in output_str
        assert map_obj.title in output_str 