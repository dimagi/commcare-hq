# Generated by Django 3.2.23 on 2024-01-29 12:28

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('geospatial', '0005_auto_20240123_1413'),
    ]

    operations = [
        migrations.RenameField(
            model_name='geoconfig',
            old_name='_api_token',
            new_name='api_token',
        ),
    ]
