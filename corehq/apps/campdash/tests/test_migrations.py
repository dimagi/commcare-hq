import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from corehq.apps.campdash.models import (
    CampaignDashboard,
    DashboardGauge,
    DashboardReport,
    DashboardMap,
)


@pytest.mark.django_db(transaction=True)
class TestMigrations:
    """Test that migrations work correctly"""

    @pytest.fixture(autouse=True)
    def setup_migration_executor(self):
        # Get the database connection
        self.connection = connection
        # Get the migration executor
        self.executor = MigrationExecutor(self.connection)
        # Get the app's migration graph
        self.app = 'campdash'
        # Get the latest migration
        self.executor.loader.build_graph()
        self.migrations = self.executor.loader.graph.nodes.keys()
        self.app_migrations = [m for m in self.migrations if m[0] == self.app]
        self.latest_migration = sorted(self.app_migrations, key=lambda m: m[1])[-1]

    def test_migration_initial_creates_models(self):
        """Test that the initial migration creates the models"""
        # Migrate to the initial migration
        initial_migration = (self.app, '0001_initial')
        self.executor.migrate([initial_migration])
        
        # Check that the models exist
        assert self._table_exists('campdash_campaigndashboard')
        assert self._table_exists('campdash_dashboardgauge')
        assert self._table_exists('campdash_dashboardreport')
        assert self._table_exists('campdash_dashboardmap')
        
        # Check that the fields exist
        assert self._field_exists('campdash_campaigndashboard', 'domain')
        assert self._field_exists('campdash_campaigndashboard', 'name')
        assert self._field_exists('campdash_campaigndashboard', 'description')
        assert self._field_exists('campdash_campaigndashboard', 'created_by')
        assert self._field_exists('campdash_campaigndashboard', 'created_on')
        assert self._field_exists('campdash_campaigndashboard', 'modified_on')
        assert self._field_exists('campdash_campaigndashboard', 'is_active')
        
        assert self._field_exists('campdash_dashboardgauge', 'dashboard_id')
        assert self._field_exists('campdash_dashboardgauge', 'title')
        assert self._field_exists('campdash_dashboardgauge', 'gauge_type')
        assert self._field_exists('campdash_dashboardgauge', 'min_value')
        assert self._field_exists('campdash_dashboardgauge', 'max_value')
        assert self._field_exists('campdash_dashboardgauge', 'current_value')
        assert self._field_exists('campdash_dashboardgauge', 'display_order')
        assert self._field_exists('campdash_dashboardgauge', 'is_active')
        
        assert self._field_exists('campdash_dashboardreport', 'dashboard_id')
        assert self._field_exists('campdash_dashboardreport', 'title')
        assert self._field_exists('campdash_dashboardreport', 'report_type')
        assert self._field_exists('campdash_dashboardreport', 'config')
        assert self._field_exists('campdash_dashboardreport', 'display_order')
        assert self._field_exists('campdash_dashboardreport', 'is_active')
        
        assert self._field_exists('campdash_dashboardmap', 'dashboard_id')
        assert self._field_exists('campdash_dashboardmap', 'title')
        assert self._field_exists('campdash_dashboardmap', 'map_type')
        assert self._field_exists('campdash_dashboardmap', 'config')
        assert self._field_exists('campdash_dashboardmap', 'display_order')
        assert self._field_exists('campdash_dashboardmap', 'is_active')

    def test_migration_sample_data_creates_data(self):
        """Test that the sample data migration creates data"""
        # Migrate to the sample data migration
        sample_data_migration = (self.app, '0002_sample_data')
        self.executor.migrate([sample_data_migration])
        
        # Check that the sample data exists
        assert CampaignDashboard.objects.filter(domain='demo').exists()
        dashboard = CampaignDashboard.objects.get(domain='demo')
        assert dashboard.name == 'Vaccination Campaign'
        
        # Check that the related data exists
        assert DashboardGauge.objects.filter(dashboard=dashboard).exists()
        assert DashboardReport.objects.filter(dashboard=dashboard).exists()
        assert DashboardMap.objects.filter(dashboard=dashboard).exists()
        
        # Check the counts
        assert DashboardGauge.objects.filter(dashboard=dashboard).count() == 3
        assert DashboardReport.objects.filter(dashboard=dashboard).count() == 1
        assert DashboardMap.objects.filter(dashboard=dashboard).count() == 1

    def test_migration_add_indexes_creates_indexes(self):
        """Test that the add indexes migration creates indexes"""
        # Migrate to the add indexes migration
        add_indexes_migration = (self.app, '0003_add_indexes')
        self.executor.migrate([add_indexes_migration])
        
        # Check that the indexes exist
        assert self._index_exists('campdash_campaigndashboard', 'campdash_domain_idx')
        assert self._index_exists('campdash_campaigndashboard', 'campdash_active_idx')
        assert self._index_exists('campdash_campaigndashboard', 'campdash_domain_active_idx')
        assert self._index_exists('campdash_dashboardgauge', 'campdash_gauge_order_idx')
        assert self._index_exists('campdash_dashboardreport', 'campdash_report_order_idx')
        assert self._index_exists('campdash_dashboardmap', 'campdash_map_order_idx')

    def test_migration_add_constraints_creates_constraints(self):
        """Test that the add constraints migration creates constraints"""
        # Migrate to the add constraints migration
        add_constraints_migration = (self.app, '0005_add_constraints')
        self.executor.migrate([add_constraints_migration])
        
        # Check that the constraints exist
        assert self._constraint_exists('campdash_campaigndashboard', 'unique_dashboard_name_per_domain')
        assert self._constraint_exists('campdash_dashboardgauge', 'gauge_min_less_than_max')
        assert self._constraint_exists('campdash_dashboardgauge', 'gauge_value_in_range')

    def _table_exists(self, table_name):
        """Check if a table exists in the database"""
        with self.connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = %s",
                [table_name]
            )
            return cursor.fetchone()[0] > 0

    def _field_exists(self, table_name, field_name):
        """Check if a field exists in a table"""
        with self.connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM information_schema.columns WHERE table_name = %s AND column_name = %s",
                [table_name, field_name]
            )
            return cursor.fetchone()[0] > 0

    def _index_exists(self, table_name, index_name):
        """Check if an index exists on a table"""
        with self.connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM pg_indexes WHERE tablename = %s AND indexname = %s",
                [table_name, index_name]
            )
            return cursor.fetchone()[0] > 0

    def _constraint_exists(self, table_name, constraint_name):
        """Check if a constraint exists on a table"""
        with self.connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM information_schema.table_constraints WHERE table_name = %s AND constraint_name = %s",
                [table_name, constraint_name]
            )
            return cursor.fetchone()[0] > 0 