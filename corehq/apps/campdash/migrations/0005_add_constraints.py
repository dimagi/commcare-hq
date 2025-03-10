from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('campdash', '0004_add_permissions'),
    ]

    operations = [
        # Add unique constraint to ensure no duplicate dashboard names within a domain
        migrations.AddConstraint(
            model_name='campaigndashboard',
            constraint=models.UniqueConstraint(
                fields=['domain', 'name'],
                name='unique_dashboard_name_per_domain'
            ),
        ),
        # Add check constraint to ensure min_value is less than max_value for gauges
        migrations.AddConstraint(
            model_name='dashboardgauge',
            constraint=models.CheckConstraint(
                check=models.Q(min_value__lt=models.F('max_value')),
                name='gauge_min_less_than_max'
            ),
        ),
        # Add check constraint to ensure current_value is between min_value and max_value
        migrations.AddConstraint(
            model_name='dashboardgauge',
            constraint=models.CheckConstraint(
                check=models.Q(current_value__gte=models.F('min_value'), 
                               current_value__lte=models.F('max_value')),
                name='gauge_value_in_range'
            ),
        ),
    ] 