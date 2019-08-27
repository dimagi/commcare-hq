
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('data_analytics', '0005_girrow'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='girrow',
            unique_together=set([('month', 'domain_name')]),
        ),
    ]
