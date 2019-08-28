
from django.db import migrations, models
import django.contrib.postgres.fields


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0004_auto_20160830_2002'),
    ]

    operations = [
        migrations.AddField(
            model_name='notification',
            name='domain_specific',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='notification',
            name='domains',
            field=django.contrib.postgres.fields.ArrayField(null=True, base_field=models.TextField(null=True, blank=True), size=None),
        ),
    ]
