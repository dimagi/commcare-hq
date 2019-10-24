from django.db import migrations, models

from corehq.util.django_migrations import AlterFieldCreateIndexIfNotExists


class Migration(migrations.Migration):

    dependencies = [
        ('icds_reports', '0138_update_thr_view'),
    ]

    operations = [
        AlterFieldCreateIndexIfNotExists(
            model_name='icdsauditentryrecord',
            name='time_of_use',
            field=models.DateTimeField(auto_now_add=True, db_index=True),
        ),
    ]
