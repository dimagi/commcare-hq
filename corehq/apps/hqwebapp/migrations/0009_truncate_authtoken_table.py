from django.db import migrations


def _truncate_authtoken_table(apps, schema_editor):
    # NOTE: truncating to preserve migration records
    from django.db import connection
    cursor = connection.cursor()
    cursor.execute("TRUNCATE TABLE `authtoken_token`")


class Migration(migrations.Migration):

    dependencies = [
        ('hqwebapp', '0008_hqoauthapplication'),
    ]

    operations = [
        migrations.RunPython(_truncate_authtoken_table, reverse_code=migrations.RunPython.noop)
    ]
