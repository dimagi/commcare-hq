from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('cleanup', '0019_alter_deletedsqldoc_table'),
    ]

    operations = [
        migrations.RunSQL("""
            DROP TABLE IF EXISTS "app_execution_appexecutionlog" CASCADE;
            DROP TABLE IF EXISTS "app_execution_appworkflowconfig" CASCADE;
        """),
    ]
