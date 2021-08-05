from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('hqadmin', '0018_back_populate_deploy_commit')
    ]

    operations = [
        migrations.RunSQL(
            "ALTER SEQUENCE IF EXISTS celery_taskmeta_id_seq MAXVALUE 2147483647 CYCLE"
        ),
    ]
