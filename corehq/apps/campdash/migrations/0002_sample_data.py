from django.db import migrations


def create_sample_data(apps, schema_editor):
    """
    Create sample campaign dashboard data for testing
    """
    CampaignDashboard = apps.get_model('campdash', 'CampaignDashboard')
    DashboardGauge = apps.get_model('campdash', 'DashboardGauge')
    DashboardReport = apps.get_model('campdash', 'DashboardReport')
    DashboardMap = apps.get_model('campdash', 'DashboardMap')
    
    # Create a sample dashboard for the 'demo' domain
    dashboard = CampaignDashboard.objects.create(
        domain='demo',
        name='Vaccination Campaign',
        description='Dashboard for tracking vaccination campaign progress',
        created_by='admin',
        is_active=True
    )
    
    # Create sample gauges
    gauges = [
        {
            'title': 'Overall Progress',
            'gauge_type': 'progress',
            'min_value': 0,
            'max_value': 100,
            'current_value': 65,
            'display_order': 0,
        },
        {
            'title': 'Completion Rate',
            'gauge_type': 'percentage',
            'min_value': 0,
            'max_value': 100,
            'current_value': 75,
            'display_order': 1,
        },
        {
            'title': 'Total Cases',
            'gauge_type': 'count',
            'min_value': 0,
            'max_value': 2000,
            'current_value': 1250,
            'display_order': 2,
        },
    ]
    
    for gauge_data in gauges:
        DashboardGauge.objects.create(
            dashboard=dashboard,
            **gauge_data
        )
    
    # Create a sample report
    report_config = {
        'headers': ['Region', 'Target', 'Completed', 'Progress'],
        'rows': [
            ['North', 500, 350, '70%'],
            ['South', 600, 390, '65%'],
            ['East', 450, 320, '71%'],
            ['West', 550, 410, '75%'],
        ],
    }
    
    DashboardReport.objects.create(
        dashboard=dashboard,
        title='Campaign Progress by Region',
        report_type='table',
        config=report_config,
        display_order=0,
    )
    
    # Create a sample map
    map_config = {
        'center': [0, 0],
        'zoom': 2,
        'markers': [
            {'lat': 40.7128, 'lng': -74.0060, 'label': 'New York', 'value': 350},
            {'lat': 34.0522, 'lng': -118.2437, 'label': 'Los Angeles', 'value': 290},
            {'lat': 41.8781, 'lng': -87.6298, 'label': 'Chicago', 'value': 210},
            {'lat': 29.7604, 'lng': -95.3698, 'label': 'Houston', 'value': 180},
        ],
    }
    
    DashboardMap.objects.create(
        dashboard=dashboard,
        title='Geographic Distribution',
        map_type='markers',
        config=map_config,
        display_order=0,
    )


def remove_sample_data(apps, schema_editor):
    """
    Remove sample data
    """
    CampaignDashboard = apps.get_model('campdash', 'CampaignDashboard')
    CampaignDashboard.objects.filter(domain='demo').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('campdash', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_sample_data, remove_sample_data),
    ] 