from django.db import migrations




class Migration(migrations.Migration):

    dependencies = [
        ('sql_proxy_accessors', '0025_index_changes'),
    ]

    operations = [
        migrations.RunSQL(
            "DROP FUNCTION IF EXISTS get_ledger_values_for_product_ids(TEXT[])",
            "SELECT 1"
        ),
    ]
