# Partially generated by Django 3.2.25 on 2024-03-25 19:26

from corehq.sql_db.operations import RawSQLMigration
from django.db import migrations, models
import django.db.models.deletion

locations_sql_migrator = RawSQLMigration(('corehq', 'apps', 'locations', 'sql_templates'), {})

class Migration(migrations.Migration):

    dependencies = [
        ('locations', '0020_delete_locationrelation'),
    ]

    operations = [
        migrations.AddField(
            model_name='locationtype',
            name='restrict_cases_to',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='locations.locationtype'),
        ),
        migrations.AlterField(
            model_name='locationtype',
            name='_expand_from',
            field=models.ForeignKey(db_column='expand_from', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='locations.locationtype'),
        ),
        migrations.AlterField(
            model_name='locationtype',
            name='expand_to',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='locations.locationtype'),
        ),
        locations_sql_migrator.get_migration('get_location_fixture_ids_2.sql'),
    ]
