# Generated by Django 2.2.16 on 2021-03-19 09:48

import corehq.motech.fhir.validators
from django.db import migrations, models
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('fhir', '0002_fhirresourcetype'),
    ]

    operations = [
        migrations.AlterField(
            model_name='fhirresourcetype',
            name='name',
            field=models.CharField(max_length=255, validators=[
                corehq.motech.fhir.validators.validate_supported_type]),
        ),
        migrations.AlterField(
            model_name='fhirresourcetype',
            name='template',
            field=jsonfield.fields.JSONField(blank=True, default=dict, null=True),
        ),
    ]
