import logging

from django.db import transaction

from dimagi.utils.couch.database import iter_docs

from corehq.apps.cleanup.management.commands.populate_sql_model_from_couch_model import PopulateSQLCommand
from corehq.apps.cloudcare.models import (
    SQLApplicationAccess,
    SQLAppGroup,
)
from corehq.dbaccessors.couchapps.all_docs import get_doc_ids_by_class

logger = logging.getLogger(__name__)


class Command(PopulateSQLCommand):
    help = """
        Adds a SQLApplicationAccess for any ApplicationAccess doc that doesn't yet have one.
    """

    @property
    def couch_class(self):
        try:
            from corehq.apps.cloudcare.models import ApplicationAccess
            return ApplicationAccess
        except ImportError:
            return None

    @property
    def couch_class_key(self):
        return set(['domain'])

    @property
    def sql_class(self):
        from corehq.apps.cloudcare.models import SQLApplicationAccess
        return SQLApplicationAccess

    def update_or_create_sql_object(self, doc):
        model, created = SQLApplicationAccess.objects.update_or_create(
            domain=doc['domain'],
            defaults={
                "restrict": doc['restrict'],
            },
        )
        model.sqlappgroup_set.all().delete()
        model.sqlappgroup_set.set([
            SQLAppGroup(app_id=group['app_id'], group_id=group['group_id'])
            for group in doc['app_groups']
        ], bulk=False)
        return (model, created)
