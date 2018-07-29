from __future__ import absolute_import
from __future__ import unicode_literals
from django.db import migrations

from corehq.motech.repeaters.models import Repeater
from corehq.motech.repeaters.utils import migrate_repeater
from corehq.sql_db.operations import HqRunPython
from corehq.util.couch import iter_update, DocUpdate


def migrate_auth_field(apps, schema_editor):
    repeater_ids = [row['id'] for row in Repeater.view(
        'repeaters/repeaters',
        include_docs=False,
        reduce=False,
        wrap_doc=False
    )]
    iter_update(
        db=Repeater.get_db(),
        fn=migrate_repeater,
        ids=repeater_ids,
    )


class Migration(migrations.Migration):

    dependencies = []

    operations = [
        HqRunPython(migrate_auth_field),
    ]
