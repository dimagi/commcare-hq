# Generated by Django 2.2.25 on 2022-02-16 09:07

import corehq.apps.domain.models
import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('domain', '0010_projectlimit'),
    ]

    operations = [
        migrations.CreateModel(
            name='AllowedDTEExpressionSettings',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('domain', models.CharField(max_length=256, unique=True)),
                ('active_dte_expressions', django.contrib.postgres.fields.ArrayField(base_field=models.CharField(choices=[('base_item', 'Base Item Expressions'), ('related_document', 'Related Document Expressions')], max_length=32), default=corehq.apps.domain.models.get_default_dte_expressions, size=None)),
            ],
        ),
    ]
