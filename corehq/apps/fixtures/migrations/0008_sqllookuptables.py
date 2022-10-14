# -*- coding: utf-8 -*-
from django.db import migrations

from ..management.commands.populate_lookuptables import Command as LookupTablesCommand
from ..management.commands.populate_lookuptablerows import Command as LookupTableRowsCommand
from ..management.commands.populate_lookuptablerowowners import Command as LookupTableRowOwnersCommand


class Migration(migrations.Migration):

    dependencies = [
        ('fixtures', '0007_db_cascade'),
    ]

    operations = [
        migrations.RunPython(
            LookupTablesCommand.migrate_from_migration,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.RunPython(
            LookupTableRowsCommand.migrate_from_migration,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.RunPython(
            LookupTableRowOwnersCommand.migrate_from_migration,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
