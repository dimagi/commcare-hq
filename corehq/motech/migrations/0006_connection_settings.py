from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('motech', '0005_requestlog_request_body'),
    ]

    operations = [
        migrations.AddField(
            model_name='connectionsettings',
            name='api_auth_settings',
            field=models.CharField(blank=True, choices=[
                (None, '(Not Applicable)'),
                ('dhis2_auth_settings', 'DHIS2 OAuth 2.0'),
                ('moveit_automation_settings', 'MOVEit Automation')
            ], max_length=64, null=True),
        ),
        migrations.AddField(
            model_name='connectionsettings',
            name='client_id',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='connectionsettings',
            name='client_secret',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='connectionsettings',
            name='last_token_aes',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AlterField(
            model_name='connectionsettings',
            name='auth_type',
            field=models.CharField(blank=True, choices=[
                (None, 'None'),
                ('basic', 'HTTP Basic'),
                ('digest', 'HTTP Digest'),
                ('oauth1', 'OAuth1'),
                ('bearer', 'Ipswitch MOVEit Automation Bearer Token'),
                ('oauth2_pwd', 'OAuth 2.0 Password Grant')
            ], max_length=16, null=True),
        ),
        migrations.AlterField(
            model_name='connectionsettings',
            name='password',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AlterField(
            model_name='connectionsettings',
            name='username',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
