from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('motech', '0005_api_auth_settings'),
    ]

    operations = [
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
