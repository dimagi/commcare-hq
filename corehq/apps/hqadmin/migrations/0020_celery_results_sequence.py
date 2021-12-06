from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('hqadmin', '0019_celery_taskmeta_sequence')
    ]

    operations = [
        migrations.RunSQL(
            "ALTER SEQUENCE IF EXISTS django_celery_results_taskresult_id_seq MAXVALUE 2147483647 CYCLE"
        ),
    ]
