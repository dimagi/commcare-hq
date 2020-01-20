import sys
import traceback

from django.core.management import call_command
from django.db import migrations

from corehq.apps.hqadmin.models import SQLHqDeploy
from corehq.dbaccessors.couchapps.all_docs import get_doc_ids_by_class
from corehq.util.django_migrations import skip_on_fresh_install


AUTO_MIGRATE_ITEMS_LIMIT = 1000
AUTO_MIGRATE_FAILED_MESSAGE = """
    A migration must be performed before this environment can be upgraded to the latest version of CommCareHQ.
    This migration is run using the management command populate_sql_hq_deploy.
"""


def count_items_to_be_migrated():
    try:
        from corehq.apps.hqadmin.models import HqDeploy
    except ImportError:
        return 0
    couch_ids = set(get_doc_ids_by_class(HqDeploy))
    sql_couch_ids = set([o.couch_id for o in SQLHqDeploy.objects.filter(couch_id__isnull=False)])
    return len(couch_ids.difference(sql_couch_ids))


@skip_on_fresh_install
def _verify_sql_hq_deploy(apps, schema_editor):
    to_migrate = count_items_to_be_migrated()
    migrated = to_migrate == 0
    if migrated:
        return

    if to_migrate < AUTO_MIGRATE_ITEMS_LIMIT:
        try:
            call_command('populate_sql_hq_deploy')
            migrated = count_items_to_be_migrated() == 0
            if not migrated:
                print("Automatic migration failed")
        except Exception:
            traceback.print_exc()
    else:
        print("Found {} items that need to be migrated.".format(to_migrate))
        print("Too many to migrate automatically.")

    if not migrated:
        print("")
        print(AUTO_MIGRATE_FAILED_MESSAGE)
        sys.exit(1)


class Migration(migrations.Migration):

    dependencies = [
        ('hqadmin', '0010_sqlhqdeploy'),
    ]

    operations = [
        migrations.RunPython(_verify_sql_hq_deploy,
                             reverse_code=migrations.RunPython.noop,
                             elidable=True),
    ]
