from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('motech', '0004_connectionsettings'),
    ]

    operations = [
        migrations.AddField(
            model_name='connectionsettings',
            name='api_auth_settings',
            field=models.CharField(blank=True, choices=[(None, '(Not Applicable)'), ('dhis2_auth_settings', 'DHIS2 OAuth 2.0'), ('moveit_automation_settings', 'MOVEit Automation')], max_length=64, null=True),
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
        migrations.AddField(
            model_name='connectionsettings',
            name='last_token_aes',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AlterField(
            model_name='connectionsettings',
            name='auth_type',
            field=models.CharField(blank=True, choices=[(None, 'None'), ('basic', 'Basic'), ('digest', 'Digest'), ('oauth1', 'OAuth1'), ('bearer', 'OAuth 2.0 Bearer Tokens')], max_length=7, null=True),
        ),
        migrations.AlterField(
            model_name='connectionsettings',
            name='password',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AlterField(
            model_name='connectionsettings',
            name='username',
            field=models.CharField(blank=True, max_length=255),
        ),
    ]
