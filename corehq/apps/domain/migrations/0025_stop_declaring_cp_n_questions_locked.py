from django.db import migrations

SET_DEFAULT = (
    'ALTER TABLE "domain_domainauditrecordentry"'
    ' ALTER COLUMN "cp_n_questions_locked" SET DEFAULT 0;'
)
DROP_DEFAULT = (
    'ALTER TABLE "domain_domainauditrecordentry"'
    ' ALTER COLUMN "cp_n_questions_locked" DROP DEFAULT;'
)


class Migration(migrations.Migration):

    dependencies = [
        ('domain', '0024_chatbotdomainsettings'),
    ]

    operations = [
        migrations.RunSQL(SET_DEFAULT, reverse_sql=DROP_DEFAULT),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(
                    model_name='domainauditrecordentry',
                    name='cp_n_questions_locked',
                ),
            ],
            database_operations=[],
        ),
    ]
