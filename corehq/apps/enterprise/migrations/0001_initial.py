# Generated by Django 2.2.20 on 2021-06-10 17:56

import django.contrib.postgres.fields
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("accounting", "0001_squashed_0052_ensure_report_builder_plans"),
    ]

    operations = [
        migrations.CreateModel(
            name='EnterprisePermissions',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_enabled', models.BooleanField(default=False)),
                ('source_domain', models.CharField(blank=True, max_length=128, null=True)),
                ('domains', django.contrib.postgres.fields.ArrayField(
                    base_field=models.CharField(max_length=128, null=True),
                    blank=True,
                    default=list,
                    null=True,
                    size=None
                )),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                              to='accounting.BillingAccount')),
            ],
        ),
    ]
