from couchdbkit import Server
from django.core.management.base import LabelCommand
from django.conf import settings
import sys
from auditcare.models import AuditEvent
from corehq.apps.domain.models import Domain
from couchforms.models import XFormInstance
from dimagi.utils.couch.database import get_db


def get_prod_db(source_uri):
    """
    Get the production database object since we need to get some doc_ids from the prod database
    """
    prod_db_name = source_uri.split('/')[-1]
    prod_server = Server(uri=source_uri[:-len(prod_db_name)])
    prod_db = prod_server.get_db(prod_db_name)
    return prod_db

class Command(LabelCommand):
    help = "Run a continuous replication of select domains"
    args = "cancel"
    label = ""

    def repl_domains(self):
        prod_db = get_prod_db(self.source_uri)
        domain_docs = [prod_db.view('domain/domains', key=x, include_docs=True, limit=1, reduce=False).one() for x in self.domain_list]
        domain_docs = filter(lambda x: x is not None, domain_docs)
        domain_doc_ids = [x['doc']['_id'] for x in domain_docs]

        if len(domain_doc_ids) == 0:
            print "No domains matching your request found, exiting to prevent a full db replication"
            sys.exit()

        params = {
            'continuous': True,
            'doc_ids': domain_doc_ids
        }

        target_server = Domain.get_db().server
        self.do_repl(target_server, params)

    def repl_docs(self):
        domain_list_string = ' '.join(self.domain_list)

        params = {
            'filter': 'fluff_filter/domain_type',
            'continuous': True,
            'query_params': {
                'domains':  domain_list_string
            }
        }

        target_server = XFormInstance.get_db().server
        self.do_repl(target_server, params)

    def repl_docs_of_type(self, doc_type):
        params = {
            'filter': 'fluff_filter/domain_type',
            'continuous': True,
            'query_params': {
                'doc_type':  doc_type
            }
        }
        target_server = get_db().server
        self.do_repl(target_server, params)

    def do_repl(self, server, params):
        if self.cancel:
            params['cancel'] = True
            print "\n\tSending a replication cancel notification to server"
        else:
            print "\n\tStarting staging replication from prod with these params: %s" % params
        server.replicate(self.source_uri, self.target_uri, **params)

    def handle(self, *args, **options):
        self.source_uri = getattr(settings, 'PRODUCTION_COUCHDB_URI', None)
        self.target_uri = XFormInstance.get_db().uri
        if self.source_uri is None:
            print "\n\tNo production URI to replicate from, we're done here.\n"
            print "\n\tNo settings.PRODUCTION_COUCHDB_URI has been set\n"
            sys.exit()

        self.domain_list = getattr(settings, 'STAGING_DOMAINS', [])
        if len(self.domain_list) == 0:
            print "\n\tUh, there aren't any domains, so this'll replicate everything, " \
                  "\n\tI don't think you want to do this." \
                  "\n\tPlease set a list of domains in localsettings.STAGING_DOMAINS " \
                  "\n\n\tgoodbye."
            sys.exit()

        if 'cancel' in args:
            self.cancel = True
        else:
            self.cancel = False

        self.repl_domains()
        self.repl_docs()
        self.repl_docs_of_type('CommCareBuild')
        self.repl_docs_of_type('CommCareBuildConfig')
        self.repl_docs_of_type('Organization')
        AuditEvent.audit_command()
