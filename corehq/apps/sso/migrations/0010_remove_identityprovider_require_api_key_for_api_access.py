from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ('sso', '0009_identityprovider_require_api_key_for_api_access'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(
                    model_name='identityprovider',
                    name='require_api_key_for_api_access',
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="ALTER TABLE sso_identityprovider "
                        "ALTER COLUMN require_api_key_for_api_access SET DEFAULT FALSE;",
                    reverse_sql="ALTER TABLE sso_identityprovider "
                                "ALTER COLUMN require_api_key_for_api_access DROP DEFAULT;",
                ),
            ],
        ),
    ]
