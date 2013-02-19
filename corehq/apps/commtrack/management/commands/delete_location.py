from django.core.management.base import BaseCommand, CommandError
from optparse import make_option
from corehq.apps.locations.models import Location
from dimagi.utils.couch.database import get_db
import sys

class Command(BaseCommand):
    args = 'loc_uuid'
#    option_list = BaseCommand.option_list + (
#         )
    help = 'DELETE a location, all its sub-locations, and all associated data'

    def handle(self, *args, **options):
        try:
            loc_uuid = args[0]
        except IndexError:
            self.stderr.write('location uuid required\n')
            return

        try:
            loc = Location.get(loc_uuid)
            if not loc or loc.doc_type != 'Location':
                raise ValueError
        except Exception:
            self.stderr.write('doc [%s] does not appear to be a location\n' % loc_uuid)
            return

        self.db = get_db()

        startkey = [loc.domain] + loc.path
        locs = Location.view('locations/hierarchy', startkey=startkey, endkey=startkey + [{}], reduce=False, include_docs=True)
        for k in locs:
            if k._id == loc._id:
                # don't delete orig loc until very end, so we can resume task if interrupted
                continue

            self.delete_doc(k, loc)

        startkey = [loc.domain, loc._id]
        linked = self.db.view('locations/linked_docs', startkey=startkey, endkey=startkey + [{}], include_docs=True)
        for k in linked:
            self.delete_doc(k['doc'], loc)

        self.delete_doc(loc, loc)

    def delete_doc(self, doc, ref):
        id = doc['_id']

        def _get(field, default=None):
            try:
                return doc[field]
            except (KeyError, AttributeError):
                return default

        domain = _get('domain')
        domains = set(_get('domains', [])).union([domain] if domain else [])
        domain = domains.pop() if len(domains) == 1 else None

        path_fields = ['location_', 'path']
        for f in path_fields:
            path = _get(f)
            if path is not None:
                break

        if domain and domain == ref.domain and path and path[:len(ref.path)] == ref.path:
            # DANGER!!
            self.db.delete_doc(id)
            self.println('deleted %s' % id)
        else:
            self.stderr.write('sanity check failed (%s)!\n' % id)
        

    def println(self, msg):
        self.stdout.write(msg + '\n')
