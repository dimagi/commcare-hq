# Makes two NOOP changes, but keeps migrations up to date with models.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('motech', '0004_connectionsettings'),
    ]

    operations = [
        migrations.AlterField(
            model_name='connectionsettings',
            name='auth_type',
            field=models.CharField(blank=True, choices=[
                (None, 'None'),
                ('basic', 'Basic'),
                ('digest', 'Digest'),
                ('oauth1', 'OAuth1'),
                ('bearer', 'Bearer'),
            ], max_length=7, null=True),
        ),
        migrations.AlterField(
            model_name='requestlog',
            name='request_body',
            field=models.TextField(blank=True, null=True),
        ),
    ]
