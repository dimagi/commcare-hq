from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('hqwebapp', '0008_hqoauthapplication'),
    ]

    operations = [
        migrations.RunSQL("""
            IF EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'authtoken_token')
            begin
                TRUNCATE TABLE authtoken_token;
            end
        """, reverse_sql=migrations.RunSQL.noop)
    ]
