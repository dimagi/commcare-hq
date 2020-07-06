# -*- coding: utf-8 -*-
# Generated by Django 1.11.28 on 2020-05-25 18:14
from __future__ import unicode_literals

from django.conf import settings
import django.contrib.postgres.fields
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def populate_api_keys(apps, schema_editor):
    TastyPieApiKey = apps.get_model('tastypie', 'ApiKey')
    ApiKeySettings = apps.get_model('hqwebapp', 'ApiKeySettings')
    HQApiKey = apps.get_model('users', 'HQApiKey')

    for api_key in TastyPieApiKey.objects.all():
        try:
            ip_allowlist = ApiKeySettings.objects.get(api_key=api_key).ip_whitelist
        except ApiKeySettings.DoesNotExist:
            ip_allowlist = []

        HQApiKey.objects.create(
            key=api_key.key,
            created=api_key.created,
            user=api_key.user,
            ip_allowlist=ip_allowlist,
        )


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('users', '0015_domainpermissionsmirror'),
    ]

    operations = [
        migrations.CreateModel(
            name='HQApiKey',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(blank=True, db_index=True, default='', max_length=128)),
                ('name', models.CharField(blank=True, default='', max_length=255)),
                ('created', models.DateTimeField(default=django.utils.timezone.now)),
                ('ip_allowlist', django.contrib.postgres.fields.ArrayField(base_field=models.GenericIPAddressField(), default=list, size=None)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='api_keys', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.RunPython(populate_api_keys, migrations.RunPython.noop)
    ]
