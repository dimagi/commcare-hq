from functools import partial

import django.contrib.postgres.fields.jsonb
import django.db.models.deletion
from django.core.management import call_command
from django.core.serializers import base, python
from django.db import migrations, models


def load_fixture(apps, schema_editor, *, fixture, app_label):
    # Credit: https://stackoverflow.com/a/39743581

    # Define a new _get_model() function here, which uses the `apps`
    # argument to get the historical version of a model, so that the
    # model matches the fixture to be loaded.
    #
    # This is an exact copy of django.core.serializers.python._get_model
    # but here it has a different context: the `apps` variable.
    def _get_model(model_identifier):
        try:
            return apps.get_model(model_identifier)
        except (LookupError, TypeError):
            raise base.DeserializationError("Invalid model identifier: '%s'" % model_identifier)

    old_get_model = python._get_model
    python._get_model = _get_model
    try:
        call_command('loaddata', fixture, app_label=app_label)
    finally:
        python._get_model = old_get_model


class Migration(migrations.Migration):

    dependencies = [
        ('motech', '0004_connectionsettings'),
    ]

    operations = [
        migrations.CreateModel(
            name='ApiAuthSettings',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('auth_type', models.CharField(choices=[
                    ('oauth1', 'OAuth1'),
                    ('bearer', 'OAuth 2.0 Bearer Tokens')
                ], max_length=7)),
                ('request_token_url', models.CharField(blank=True, max_length=255, null=True)),
                ('authorization_url', models.CharField(blank=True, max_length=255, null=True)),
                ('access_token_url', models.CharField(blank=True, max_length=255, null=True)),
                ('token_url', models.CharField(blank=True, max_length=255, null=True)),
                ('refresh_url', models.CharField(blank=True, max_length=255, null=True)),
                ('pass_credentials_in_header', models.BooleanField(default=False)),
            ],
        ),
        migrations.AddField(
            model_name='connectionsettings',
            name='last_token',
            field=django.contrib.postgres.fields.jsonb.JSONField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='connectionsettings',
            name='auth_type',
            field=models.CharField(blank=True, choices=[
                (None, 'None'),
                ('basic', 'Basic'),
                ('digest', 'Digest'),
                ('oauth1', 'OAuth1'),
                ('bearer', 'OAuth 2.0 Bearer Tokens')
            ], max_length=7, null=True),
        ),
        migrations.AddField(
            model_name='connectionsettings',
            name='api_auth_settings',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to='motech.ApiAuthSettings'
            ),
        ),
        migrations.AddField(
            model_name='connectionsettings',
            name='client_id',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='connectionsettings',
            name='client_secret',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),

        # Load initial data
        migrations.RunPython(partial(
            load_fixture,
            fixture='corehq/motech/fixtures/motech/api_auth_settings.json',
            app_label='motech.ApiAuthSettings',
        )),
    ]
