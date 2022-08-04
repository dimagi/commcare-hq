from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('hqwebapp', '0008_hqoauthapplication'),
    ]

    operations = [
        migrations.RunSQL("""
            DROP TABLE IF EXISTS authtoken_token;
            DELETE FROM django_migrations WHERE app='authtoken';
        """, reverse_sql=migrations.RunSQL.noop)
    ]
