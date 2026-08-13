from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('sso', '0010_remove_identityprovider_require_api_key_for_api_access'),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE sso_identityprovider "
                "DROP COLUMN require_api_key_for_api_access;",
            reverse_sql="ALTER TABLE sso_identityprovider "
                        "ADD COLUMN require_api_key_for_api_access "
                        "BOOLEAN NOT NULL DEFAULT FALSE;",
        ),
    ]
