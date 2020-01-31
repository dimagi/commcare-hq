from django.db import migrations

from corehq.apps.hqadmin.management.commands.populate_sql_hq_deploy import Command


class Migration(migrations.Migration):

    dependencies = [
        ('hqadmin', '0010_sqlhqdeploy'),
    ]

    operations = [
        migrations.RunPython(Command.migrate_from_migration,
                             reverse_code=migrations.RunPython.noop,
                             elidable=True),
    ]
