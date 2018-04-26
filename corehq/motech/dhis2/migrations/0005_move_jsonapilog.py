from __future__ import unicode_literals
from __future__ import absolute_import
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('dhis2', '0004_auto_20171122_0827'),
    ]

    database_operations = [
        migrations.AlterModelTable('JsonApiLog', 'motech_requestlog')
    ]

    state_operations = [
        migrations.DeleteModel('JsonApiLog')
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=database_operations,
            state_operations=state_operations)
    ]
