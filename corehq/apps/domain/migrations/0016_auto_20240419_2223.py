import corehq.apps.domain.models
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('domain', '0015_domainsettings'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='domainsettings',
            options={'verbose_name_plural': 'domain settings'},
        ),
        migrations.AlterModelOptions(
            name='operatorcalllimitsettings',
            options={'verbose_name_plural': 'operator call limit settings'},
        ),
        migrations.AlterField(
            model_name='domainsettings',
            name='redirect_base_url',
            field=corehq.apps.domain.models.SecureURLField(
                blank=True,
                default='',
                max_length=255,
                verbose_name='Redirect base URL',
            ),
        ),
    ]
