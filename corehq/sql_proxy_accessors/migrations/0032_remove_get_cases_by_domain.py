
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sql_proxy_accessors', '0031_write_blob_bucket'),
    ]

    operations = [
        migrations.RunSQL("DROP FUNCTION IF EXISTS get_case_types_for_domain(TEXT)")
    ]
