# Generated by Django 3.2.25 on 2024-04-02 20:54
from django.core.management import call_command
from django.db import migrations, models
import django.db.models.deletion

from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def copy_invitation_supply_point(apps, schema_editor):
    call_command('copy_invitation_supply_point')


class Migration(migrations.Migration):

    dependencies = [
        ('locations', '0020_delete_locationrelation'),
        ('custom_data_fields', '0008_custom_data_fields_upstream_ids'),
        ('users', '0057_populate_sql_user_data'),
    ]

    operations = [
        migrations.AddField(
            model_name='invitation',
            name='custom_user_data',
            field=models.JSONField(default=dict),
        ),
        migrations.AddField(
            model_name='invitation',
            name='location',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='locations.sqllocation', to_field='location_id'),
        ),
        migrations.AddField(
            model_name='invitation',
            name='profile',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='custom_data_fields.customdatafieldsprofile'),
        ),
        migrations.RunPython(copy_invitation_supply_point, migrations.RunPython.noop),
    ]
