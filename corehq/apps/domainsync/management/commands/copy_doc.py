from couchdbkit import Database
from dimagi.utils.couch.database import get_db
from django.core.management.base import LabelCommand, CommandError
from corehq.apps.domainsync.config import DocumentTransform, save


class Command(LabelCommand):
    help = "Copy any couch doc"
    args = '<sourcedb> <doc_id> (<domain>)'
    label = ""

    def handle(self, *args, **options):
        if len(args) < 2 or len(args) > 3:
            raise CommandError('Usage is copy_doc %s' % self.args)

        sourcedb = Database(args[0])
        doc_id = args[1]
        domain = args[2] if len(args) == 3 else None

        doc_json = sourcedb.get(doc_id)
        if domain:
            doc_json['domain'] = domain
        dt = DocumentTransform(doc_json, sourcedb)
        save(dt, get_db())
