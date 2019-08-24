
from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('data_interfaces', '0003_update__automaticupdaterulecriteria__match_type__choices'),
    ]

    operations = [
        migrations.AddField(
            model_name='automaticupdateaction',
            name='property_value_type',
            field=models.CharField(default=b'EXACT', max_length=15),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='automaticupdaterule',
            name='filter_on_server_modified',
            field=models.BooleanField(default=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='automaticupdaterule',
            name='server_modified_boundary',
            field=models.IntegerField(null=True),
            preserve_default=True,
        ),
    ]
