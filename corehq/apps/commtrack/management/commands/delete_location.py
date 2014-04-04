from optparse import make_option
from django.core.management.base import BaseCommand
from corehq.apps.locations.models import Location
from dimagi.utils.couch.database import get_db

class Command(BaseCommand):
    args = 'loc_uuid'
    help = 'DELETE a location, all its sub-locations, and all associated data'
    option_list = BaseCommand.option_list + (
        make_option('--dryrun',
                    action='store_true',
                    dest='dryrun',
                    default=False,
                    help='Do not actually delete anything, just verbosely log what happens.'),
        make_option('--bulk',
                    action='store_true',
                    dest='bulk',
                    default=False,
                    help='Instead of passing an ID, pass a text file containing one line per ID.'),
    )


    def handle(self, *args, **options):
        self.dryrun = options['dryrun']
        self.bulk = options['bulk']
        try:
            arg = args[0]
        except IndexError:
            self.stderr.write('location uuid required\n')
            return

        if not self.bulk:
            self._delete_location_id(arg)
        else:
            with open(arg) as f:
                for line in f:
                    self._delete_location_id(line.strip())

    def _delete_location_id(self, loc_uuid):
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
        success = True
        for k in linked:
            success = success and self.delete_doc(k['doc'], loc)

        if success:
            self.println('deleted location %s (%s)' % (loc._id, loc.name))
            if not self.dryrun:
                self.db.delete_doc(loc)
        else:
            self.stderr.write('not deleting %s because there were errors' % loc._id)

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
            self.println('deleted %s (%s:%s)' %
                (id, doc.get('doc_type', 'unknown type'), doc.get('name', 'unknown name'))
            )
            if not self.dryrun:
                self.db.delete_doc(id)
            return True
        else:
            self.stderr.write('sanity check failed (%s)!\n' % id)
            return False
        

    def println(self, msg):
        self.stdout.write(msg + '\n')
