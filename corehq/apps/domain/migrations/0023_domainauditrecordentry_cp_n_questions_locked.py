from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('domain', '0022_domainauditrecordentry_cp_n_enterprise_console_exports_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='domainauditrecordentry',
            name='cp_n_questions_locked',
            field=models.BigIntegerField(default=0),
        ),
    ]
