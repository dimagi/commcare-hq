# Generated by Django 3.2.18 on 2023-04-27 06:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('data_dictionary', '0012_populate_case_property_groups'),
    ]

    operations = [
        migrations.AddField(
            model_name='casepropertygroup',
            name='deprecated',
            field=models.BooleanField(default=False),
        ),
    ]
