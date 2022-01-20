from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('data_interfaces', '0024_add_automaticupdaterule_upstream_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='domaincaserulerun',
            name='num_errors',
            field=models.IntegerField(default=0),
        ),
    ]
