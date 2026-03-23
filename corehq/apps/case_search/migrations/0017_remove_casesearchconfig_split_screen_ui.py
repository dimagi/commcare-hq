from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("case_search", "0016_csqlfixtureexpression_user_data_criteria"),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE case_search_casesearchconfig DROP COLUMN IF EXISTS split_screen_ui",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
