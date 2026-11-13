# Remove Road Network Algorithm feature
# Migrate existing configs to Radial Algorithm and remove related fields

from django.db import migrations, models


def migrate_road_network_to_radial(apps, schema_editor):
    """Migrate any GeoConfig instances using road_network_algorithm to radial_algorithm"""
    GeoConfig = apps.get_model('geospatial', 'GeoConfig')
    updated_count = GeoConfig.objects.filter(
        selected_disbursement_algorithm='road_network_algorithm'
    ).update(
        selected_disbursement_algorithm='radial_algorithm'
    )
    if updated_count:
        print(f"Migrated {updated_count} GeoConfig instance(s) from road_network to radial algorithm")


class Migration(migrations.Migration):

    dependencies = [
        ('geospatial', '0009_geoconfig_api_key_cbc_encryption'),
    ]

    operations = [
        # First migrate data from road_network to radial
        migrations.RunPython(migrate_road_network_to_radial, migrations.RunPython.noop),
        # Then remove the fields that were only used by Road Network Algorithm
        migrations.RemoveField(
            model_name='geoconfig',
            name='travel_mode',
        ),
        migrations.RemoveField(
            model_name='geoconfig',
            name='api_token',
        ),
        migrations.AlterField(
            model_name='geoconfig',
            name='selected_disbursement_algorithm',
            field=models.CharField(
                choices=[('radial_algorithm', 'Radial Algorithm')],
                default='radial_algorithm',
                max_length=50,
            ),
        ),
    ]
