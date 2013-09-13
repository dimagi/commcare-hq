from django.core.management.base import LabelCommand
from django.conf import settings
import sys
from couchforms.models import XFormInstance


class Command(LabelCommand):
    help = "Run a blocking replication of select domains"
    args = "cancel"
    label = ""

    def handle(self, *args, **options):
        source_uri = getattr(settings, 'PRODUCTION_COUCHDB_URI', None)
        target_uri = XFormInstance.get_db().uri
        if source_uri is None:
            print "\n\tNo production URI to replicate from, we're done here.\n"
            sys.exit()

        domain_list = getattr(settings, 'STAGING_DOMAINS', [])
        if len(domain_list) == 0:
            print "\n\tUh, there aren't any domains, so this'll replicate everything, " \
                  "\n\tI don't think you want to do this." \
                  "\n\tPlease set a list of domains in localsettings.STAGING_DOMAINS " \
                  "\n\n\tgoodbye."
            sys.exit()

        domain_list_string = ' '.join(domain_list)
        repl_params = {
            'filter': 'fluff_filter/domain_type',
            'continuous': True,
            'query_params': {
                'domains':  domain_list_string
            }
        }

        if 'cancel' in args:
            repl_params['cancel'] = True
            print "\n\tSending a replication cancel notification to server"
        else:
            print "\n\tStarting staging replication from prod with these params: %s" % repl_params

        server = XFormInstance.get_db().server
        #import ipdb;ipdb.set_trace()
        #server.replicate(source_uri, target_uri, **repl_params)


