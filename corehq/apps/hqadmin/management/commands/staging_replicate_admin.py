import copy
from optparse import make_option
from django.core.management.base import LabelCommand
from django.conf import settings
import sys
import simplejson
from auditcare.models import AuditEvent
from corehq.apps.users.models import CommCareUser
from corehq.pillows.user import UserPillow
from couchforms.models import XFormInstance

BASE_QUERY = "is_superuser: true"

QUERY_DICT = {
    "query": {
        "filtered": {
            "query": {
                "query_string": {
                    "query": ""
                }
            }
        }
    }
}

def get_query(query_string, start=0, size=25):
    ret = copy.deepcopy(QUERY_DICT)
    ret['query']['filtered']['query']['query_string']['query'] = query_string
    ret['from'] = start
    ret['size'] = size
    return ret


def get_query_results(es, query_string, start=0, size=100):
    def get_results(query_string, st, sz):
        return es.post("_search", data=get_query(query_string, start=st, size=sz))

    search_results = get_results(query_string, start, size)
    print "### total users in query: %s" % search_results['hits']['total']

    yielded = 0
    while yielded < search_results['hits']['total']:
        for res in search_results['hits']['hits']:
            if '_source' in res:
                #print "\tUser [%s]: %s, is_superuser: %s" % (yielded, res['_source']['username'], res['_source']['is_superuser'])
                yield res['_source']
            yielded += 1
        new_start = yielded
        search_results = get_results(query_string, new_start, size)

class Command(LabelCommand):
    help = "Run a continuous replication of administrative users for your staging environment"
    args = "cancel"
    label = ""

    option_list = LabelCommand.option_list + \
                  (
                      make_option('--query',
                                  action='store',
                                  dest='query_string',
                                  default=None,
                                  help="Single Pillow class to flip alias"),
                      make_option('--makeitso',
                                  action='store_true',
                                  dest='makeitso',
                                  default=False,
                                  help="Actually start replication"),
                  )

    def handle(self, *args, **options):
        source_uri = getattr(settings, 'PRODUCTION_COUCHDB_URI', None)
        target_uri = XFormInstance.get_db().uri
        if source_uri is None:
            print "\n\tNo production URI to replicate from, we're done here.\n"
            print "\n\tNo settings.PRODUCTION_COUCHDB_URI has been set\n"
            sys.exit()

        input_query = options['query_string']

        if not input_query:
            print "\tRunning default admins query"
            query_string = BASE_QUERY

        else:
            query_string = input_query

        print "\n\tRunning user query: %s" % query_string

        user_pillow = UserPillow()
        user_es = user_pillow.get_es()

        doc_ids = [res['_id'] for res in get_query_results(user_es, query_string)]

        do_replicate = options['makeitso']
        repl_params = {
            'doc_ids': doc_ids
        }

        if 'cancel' in args:
            repl_params['cancel'] = True
            print "\n\tSending a replication cancel notification to server"
        else:
            print "\n\tStarting staging replication from prod"

        if do_replicate:
            server = CommCareUser.get_db().server
            server.replicate(source_uri, target_uri, **repl_params)
            AuditEvent.audit_command()
        else:
            print "\n\tReplication dry run with params: %s" % repl_params


