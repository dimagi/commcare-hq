from couchdbkit.exceptions import ResourceNotFound
from gevent import monkey; monkey.patch_all()
import sys
import gevent
from restkit.session import set_session
set_session("gevent")
from gevent.pool import Pool
from django.core.management.base import BaseCommand

from django.conf import settings
setattr(settings, 'COUCHDB_TIMEOUT', 999999)
from couchdbkit.ext.django.loading import get_db

DESIGN_DOC_VIEW = '_all_docs'
DESIGN_SK = "_design"
DESIGN_EK = "_design0"

POOL_SIZE=12
REPEAT_INTERVAL = getattr(settings,'PRIME_VIEWS_INTERVAL', 3600)

#apps_with_dbs = [
#    'couchforms', #commcarehq for everything
#    'auditcare',
#    'couchlog',
#    ]

def get_unique_dbs():
    """
    In order to not break abstraction barrier, we walk through all the COUCH_DATABASES
    and assemble the unique set of databases (based upon the URL) to prime the views and all the design docs in it.
    """
    ret = []
    seen_dbs = []
    db_apps = settings.COUCHDB_DATABASES
    for t in db_apps:
        app_name = t[0]
        url = t[1]
        db_name = t[0].split('/')[-1]
        if db_name in seen_dbs:
            continue
        else:
            seen_dbs.append(db_name)
            ret.append(app_name)
    return ret


def do_prime(app_label, design_doc_name, view_name, verbose=False):
    db = get_db(app_label)
#    print "start priming %s:%s/%s" % (app_label, design_doc_name, view_name)
    try:
        list(db.view('%s/%s' % (design_doc_name, view_name), limit=0))
        if verbose:
            sys.stdout.write('.')
            sys.stdout.flush()
    except ResourceNotFound:
        if verbose:
            sys.stdout.write('!=>%s/%s/%s' % (app_label,design_doc_name, view_name))
            sys.stdout.flush()
#    print "done priming %s:%s/%s" % (app_label, design_doc_name, view_name)

class Command(BaseCommand):
    help = 'Sync live design docs with gevent'

    def handle(self, *args, **options):
#        print "priming views"
        pool = Pool(POOL_SIZE)

        while True:
            self.prime_everything(pool)
            gevent.sleep(REPEAT_INTERVAL)
#            print "exited main app loop - repeating after %s pause" % REPEAT_INTERVAL
#        print "done!"

    def prime_everything(self, pool, verbose=False):
        unique_dbs = get_unique_dbs()
        for app in unique_dbs:
            try:
                db = get_db(app)
                design_docs = db.view(DESIGN_DOC_VIEW, startkey=DESIGN_SK, endkey=DESIGN_EK, include_docs=True).all()
                for res in design_docs:
                    design_doc = res['doc']
                    design_doc_name = design_doc['_id'].split('/')[-1] # _design/app_name
                    if design_doc_name.endswith('-tmp'):
                        #it's a dangling -tmp preindex view, skip
                        continue
                    else:
                        views = design_doc.get('views', {})
                        #get the first view
                        for view_name in views.keys():
                            pool.spawn(do_prime, app, design_doc_name, view_name, verbose=verbose)
                            break
            except Exception, ex:
                #print "Got an exception but ignoring: %s" % ex
                pass
