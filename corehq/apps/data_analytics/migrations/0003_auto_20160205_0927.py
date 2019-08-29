
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('data_analytics', '0002_maltrow_threshold'),
    ]

    operations = [
        migrations.AddField(
            model_name='maltrow',
            name='device_id',
            field=models.TextField(null=True, blank=True),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='maltrow',
            unique_together=set([('month', 'domain_name', 'user_id', 'app_id', 'device_id')]),
        ),
    ]
