# Generated by Django 4.2.11 on 2024-06-18 14:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('locations', '0021_add_fixture_queryset_case_sync_restriction'),
    ]

    operations = [
        migrations.AddField(
            model_name='locationtype',
            name='has_users',
            field=models.BooleanField(default=True),
        ),
    ]
