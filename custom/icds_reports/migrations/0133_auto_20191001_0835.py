from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('icds_reports', '0132_update_nic_view'),
    ]

    operations = [
        migrations.DeleteModel(
            name='CitusDashboardDiff',
        ),
        migrations.DeleteModel(
            name='CitusDashboardException',
        ),
        migrations.DeleteModel(
            name='CitusDashboardTiming',
        ),
    ]
