from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('campdash', '0002_sample_data'),
    ]

    operations = [
        # Add index to domain field for faster lookups
        migrations.AddIndex(
            model_name='campaigndashboard',
            index=models.Index(fields=['domain'], name='campdash_domain_idx'),
        ),
        # Add index to is_active field for filtering active dashboards
        migrations.AddIndex(
            model_name='campaigndashboard',
            index=models.Index(fields=['is_active'], name='campdash_active_idx'),
        ),
        # Add composite index for domain and is_active for common queries
        migrations.AddIndex(
            model_name='campaigndashboard',
            index=models.Index(fields=['domain', 'is_active'], name='campdash_domain_active_idx'),
        ),
        # Add indexes for gauge display order for sorting
        migrations.AddIndex(
            model_name='dashboardgauge',
            index=models.Index(fields=['display_order'], name='campdash_gauge_order_idx'),
        ),
        # Add indexes for report display order for sorting
        migrations.AddIndex(
            model_name='dashboardreport',
            index=models.Index(fields=['display_order'], name='campdash_report_order_idx'),
        ),
        # Add indexes for map display order for sorting
        migrations.AddIndex(
            model_name='dashboardmap',
            index=models.Index(fields=['display_order'], name='campdash_map_order_idx'),
        ),
    ] 