import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from corehq.apps.campdash.models import (
    CampaignDashboard,
    DashboardGauge,
    DashboardReport,
    DashboardMap,
)


class TestCampaignDashboard:
    """Test cases for the CampaignDashboard model"""

    @pytest.fixture(autouse=True)
    def setup(self, db):
        self.dashboard = CampaignDashboard.objects.create(
            domain='test-domain',
            name='Test Dashboard',
            description='Test dashboard description',
            created_by='test-user',
            is_active=True
        )

    def test_dashboard_creation(self):
        """Test that a dashboard can be created with valid data"""
        assert self.dashboard.domain == 'test-domain'
        assert self.dashboard.name == 'Test Dashboard'
        assert self.dashboard.description == 'Test dashboard description'
        assert self.dashboard.created_by == 'test-user'
        assert self.dashboard.is_active is True
        assert self.dashboard.created_on is not None
        assert self.dashboard.modified_on is not None

    def test_dashboard_str_representation(self):
        """Test the string representation of a dashboard"""
        assert str(self.dashboard) == 'Test Dashboard (test-domain)'

    def test_unique_constraint(self):
        """Test that the unique constraint for domain and name works"""
        # Creating a dashboard with the same domain and name should raise an error
        with pytest.raises(IntegrityError):
            CampaignDashboard.objects.create(
                domain='test-domain',
                name='Test Dashboard',
                created_by='test-user'
            )

        # Creating a dashboard with the same name but different domain should work
        dashboard2 = CampaignDashboard.objects.create(
            domain='other-domain',
            name='Test Dashboard',
            created_by='test-user'
        )
        assert dashboard2.domain == 'other-domain'
        assert dashboard2.name == 'Test Dashboard'


class TestDashboardGauge:
    """Test cases for the DashboardGauge model"""

    @pytest.fixture(autouse=True)
    def setup(self, db):
        self.dashboard = CampaignDashboard.objects.create(
            domain='test-domain',
            name='Test Dashboard',
            created_by='test-user'
        )
        self.gauge = DashboardGauge.objects.create(
            dashboard=self.dashboard,
            title='Test Gauge',
            gauge_type='progress',
            min_value=0,
            max_value=100,
            current_value=50,
            display_order=1
        )

    def test_gauge_creation(self):
        """Test that a gauge can be created with valid data"""
        assert self.gauge.dashboard == self.dashboard
        assert self.gauge.title == 'Test Gauge'
        assert self.gauge.gauge_type == 'progress'
        assert self.gauge.min_value == 0
        assert self.gauge.max_value == 100
        assert self.gauge.current_value == 50
        assert self.gauge.display_order == 1
        assert self.gauge.is_active is True

    def test_gauge_str_representation(self):
        """Test the string representation of a gauge"""
        assert str(self.gauge) == 'Test Gauge - Test Dashboard'

    def test_gauge_validation(self):
        """Test that gauge validation works correctly"""
        # Test min_value < max_value constraint
        gauge = DashboardGauge(
            dashboard=self.dashboard,
            title='Invalid Gauge',
            gauge_type='progress',
            min_value=100,
            max_value=50,
            current_value=75
        )
        with pytest.raises(ValidationError):
            gauge.clean()

        # Test current_value in range constraint
        gauge = DashboardGauge(
            dashboard=self.dashboard,
            title='Invalid Gauge',
            gauge_type='progress',
            min_value=0,
            max_value=100,
            current_value=150
        )
        with pytest.raises(ValidationError):
            gauge.clean()

        gauge = DashboardGauge(
            dashboard=self.dashboard,
            title='Invalid Gauge',
            gauge_type='progress',
            min_value=0,
            max_value=100,
            current_value=-10
        )
        with pytest.raises(ValidationError):
            gauge.clean()


class TestDashboardReport:
    """Test cases for the DashboardReport model"""

    @pytest.fixture(autouse=True)
    def setup(self, db):
        self.dashboard = CampaignDashboard.objects.create(
            domain='test-domain',
            name='Test Dashboard',
            created_by='test-user'
        )
        self.report = DashboardReport.objects.create(
            dashboard=self.dashboard,
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

    def test_report_creation(self):
        """Test that a report can be created with valid data"""
        assert self.report.dashboard == self.dashboard
        assert self.report.title == 'Test Report'
        assert self.report.report_type == 'table'
        assert self.report.display_order == 1
        assert self.report.is_active is True
        assert len(self.report.config['rows']) == 2
        assert len(self.report.config['headers']) == 4

    def test_report_str_representation(self):
        """Test the string representation of a report"""
        assert str(self.report) == 'Test Report - Test Dashboard'


class TestDashboardMap:
    """Test cases for the DashboardMap model"""

    @pytest.fixture(autouse=True)
    def setup(self, db):
        self.dashboard = CampaignDashboard.objects.create(
            domain='test-domain',
            name='Test Dashboard',
            created_by='test-user'
        )
        self.map = DashboardMap.objects.create(
            dashboard=self.dashboard,
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

    def test_map_creation(self):
        """Test that a map can be created with valid data"""
        assert self.map.dashboard == self.dashboard
        assert self.map.title == 'Test Map'
        assert self.map.map_type == 'markers'
        assert self.map.display_order == 1
        assert self.map.is_active is True
        assert len(self.map.config['markers']) == 2
        assert self.map.config['zoom'] == 2

    def test_map_str_representation(self):
        """Test the string representation of a map"""
        assert str(self.map) == 'Test Map - Test Dashboard' 