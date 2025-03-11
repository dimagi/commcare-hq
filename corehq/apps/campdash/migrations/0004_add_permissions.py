from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('campdash', '0003_add_indexes'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='campaigndashboard',
            options={
                'app_label': 'campdash',
                'permissions': [
                    ('view_all_campaign_dashboards', 'Can view all campaign dashboards'),
                    ('edit_all_campaign_dashboards', 'Can edit all campaign dashboards'),
                ],
            },
        ),
        migrations.AlterModelOptions(
            name='dashboardgauge',
            options={
                'app_label': 'campdash',
                'ordering': ['display_order'],
                'permissions': [
                    ('configure_gauges', 'Can configure dashboard gauges'),
                ],
            },
        ),
        migrations.AlterModelOptions(
            name='dashboardreport',
            options={
                'app_label': 'campdash',
                'ordering': ['display_order'],
                'permissions': [
                    ('configure_reports', 'Can configure dashboard reports'),
                ],
            },
        ),
        migrations.AlterModelOptions(
            name='dashboardmap',
            options={
                'app_label': 'campdash',
                'ordering': ['display_order'],
                'permissions': [
                    ('configure_maps', 'Can configure dashboard maps'),
                ],
            },
        ),
    ] 