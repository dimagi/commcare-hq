from django.db import migrations

from corehq.util.django_migrations import add_if_not_exists


class Migration(migrations.Migration):

    dependencies = [
        ('hqwebapp', '0008_hqoauthapplication'),
    ]

    operations = [
        migrations.RunSQL(add_if_not_exists("TRUNCATE TABLE authtoken_token"), reverse_sql=migrations.RunSQL.noop)
    ]
