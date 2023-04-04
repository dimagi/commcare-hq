from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('motech', '0011_connectionsettings_is_deleted'),
    ]

    operations = [
        migrations.AlterField(
            model_name='connectionsettings',
            name='auth_type',
            field=models.CharField(
                blank=True,
                choices=[
                    (None, 'None'),
                    ('basic', 'HTTP Basic'),
                    ('digest', 'HTTP Digest'),
                    ('oauth1', 'OAuth1'),
                    ('oauth2_client', 'OAuth 2.0 Client Credentials Grant'),
                    ('oauth2_pwd', 'OAuth 2.0 Password Grant'),
                    ('bearer', 'Bearer Token')
                ],
                max_length=16,
                null=True,
            ),
        ),
    ]
