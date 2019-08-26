
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sql_proxy_accessors', '0032_remove_get_cases_by_domain'),
    ]

    operations = [
        migrations.RunSQL("DROP FUNCTION IF EXISTS case_modified_since(TEXT, TIMESTAMP)")
    ]
