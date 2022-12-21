from django.db import migrations

from corehq.util.django_migrations import execute_sql_if_exists_raw


class Migration(migrations.Migration):

    dependencies = [
        ('hqwebapp', '0008_hqoauthapplication'),
    ]

    operations = [
        migrations.RunSQL(
            execute_sql_if_exists_raw("TRUNCATE TABLE authtoken_token", name='authtoken_table'),
            reverse_sql=migrations.RunSQL.noop
        )
    ]
