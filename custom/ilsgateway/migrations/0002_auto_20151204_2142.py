from django.db import models, migrations
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ilsgateway', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='historicallocationgroup',
            name='location_id',
            field=models.ForeignKey(to='locations.SQLLocation', on_delete=django.db.models.deletion.PROTECT),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='ilsnotes',
            name='location',
            field=models.ForeignKey(to='locations.SQLLocation', on_delete=django.db.models.deletion.PROTECT),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='reportrun',
            name='location',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='locations.SQLLocation', null=True),
            preserve_default=True,
        ),
    ]
