
from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('data_analytics', '0006_unique_girrow'),
    ]

    operations = [
        migrations.AddField(
            model_name='girrow',
            name='eligible_forms',
            field=models.PositiveIntegerField(default=0),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='girrow',
            name='experienced_threshold',
            field=models.PositiveIntegerField(null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='girrow',
            name='performance_threshold',
            field=models.PositiveIntegerField(null=True),
            preserve_default=True,
        ),
    ]
