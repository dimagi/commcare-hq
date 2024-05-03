import logging
from collections import defaultdict

from django.core.management.base import BaseCommand

from corehq.apps.export.models import FormExportDataSchema

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = """"Once-off command to rebuild schemas affected by subcase in repeat bug

    See https://github.com/dimagi/commcare-hq/pull/21384
    """

    def handle(self, **options):
        schemas_to_rebuild = defaultdict(list)
        for doc_id, domain, app_id, xmlns in _latest_form_schema_ids():
            schema = FormExportDataSchema.get(doc_id)
            group_schemas = schema.group_schemas[1:]
            for gs in group_schemas:
                if not gs.path[-1].is_repeat:
                    schemas_to_rebuild[domain].append((app_id, xmlns))
                    break

        for domain, schema_keys in schemas_to_rebuild.items():
            print("Rebuilding {} schemas for domain '{}'".format(len(schema_keys), domain))
            for app_id, xmlns in schema_keys:
                print("    rebuilding ('{}', '{}')".format(app_id, xmlns))
                FormExportDataSchema.generate_schema(domain, app_id, xmlns, force_rebuild=True)


def _latest_form_schema_ids():
    db = FormExportDataSchema.get_db()
    seen = set()
    for row in db.view('schemas_by_xmlns_or_case_type/view', reduce=False, descending=True):
        key_ = row['key']
        doc_type = key_[1]
        if doc_type != 'FormExportDataSchema':
            continue

        domain, doc_type, app_id, xmlns, created_on = key_
        doc_key = (domain, app_id, xmlns)
        if doc_key in seen:
            continue

        seen.add(doc_key)
        yield row['id'], domain, app_id, xmlns
