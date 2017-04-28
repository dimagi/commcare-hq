from django.db import migrations

from corehq.apps.repeaters.models import Repeater
from corehq.sql_db.operations import HqRunPython
from corehq.util.couch import iter_update, DocUpdate


def migrate_auth_field(apps, schema_editor):
    repeater_ids = [row['id'] for row in Repeater.view(
        'receiverwrapper/repeaters',
        include_docs=False,
        reduce=False,
        wrap_doc=False
    )]
    iter_update(
        db=Repeater.get_db(),
        fn=migrate_repeater,
        ids=repeater_ids,
    )


def migrate_repeater(repeater_doc):
    if "use_basic_auth" in repeater_doc:
        use_basic_auth = repeater_doc['use_basic_auth'] == True
        del repeater_doc['use_basic_auth']
        if use_basic_auth:
            repeater_doc["auth_type"] = "basic"
        return DocUpdate(repeater_doc)


class Migration(migrations.Migration):

    dependencies = []

    operations = [
        HqRunPython(migrate_auth_field),
    ]
