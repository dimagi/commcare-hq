from django.core.management.base import BaseCommand

from corehq.form_processor.models import XFormInstance
from corehq.sql_db.util import get_db_aliases_for_partitioned_query


class Command(BaseCommand):
    help = "One time use. Populate missing XFormInstance.deleted_on values"

    def handle(self, **options):
        for db in get_db_aliases_for_partitioned_query():
            queryset = XFormInstance.objects.using(db).filter(deleted_on__isnull=True)
            for xform in queryset:
                if xform.doc_type == 'XFormInstance-Deleted':
                    xform.deleted_on = xform.server_modified_on
                    xform.save()
