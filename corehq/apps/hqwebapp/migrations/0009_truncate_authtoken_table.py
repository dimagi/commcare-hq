from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('hqwebapp', '0008_hqoauthapplication'),
    ]

    operations = [
        migrations.RunSQL("TRUNCATE TABLE authtoken_token", reverse_sql=migrations.RunSQL.noop)
    ]
