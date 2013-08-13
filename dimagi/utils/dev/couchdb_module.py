# -*- coding: utf-8 -
from devserver.modules import DevServerModule
from django.conf import settings
import couchdbkit
from dimagi.utils.couch.debugdb import debugdatabase, OPEN_DOC_OUTPUT_HEADERS, VIEW_OUTPUT_HEADERS


SHOW_VERBOSE = getattr(settings, 'COUCHDB_DEVSERVER_VERBOSE', False)

class CouchDBDevModule(DevServerModule):
    """
    A couchdb console output module for the django devserver https://github.com/dcramer/django-devserver
    """
    logger_name = 'couchdbkit'
    couchdbkit.client.Database = debugdatabase.DebugDatabase
    couchdbkit.client.ViewResults = debugdatabase.DebugViewResults

    def process_request(self, request):
        self.logger.info('Request started')
        self.view_offset = len(getattr(couchdbkit.client.ViewResults, '_queries', []))
        self.get_offset = len(getattr(couchdbkit.client.Database, '_queries', []))


    def process_response(self, request, response):
        self.logger.info('Request ended')
        gets = getattr(debugdatabase.DebugDatabase, '_queries', [])
        views = getattr(debugdatabase.DebugViewResults, '_queries', [])

        if SHOW_VERBOSE:
            self.logger.debug("GET raw output")
            for r in gets:
                outstring = ", ".join(['%s: %s' % (h, r[h]) for h in OPEN_DOC_OUTPUT_HEADERS])
                self.logger.info("Couch GET %s" % outstring)


            for v in views:
                outstring = ", ".join(['%s: %s' % (h, v[h]) for h in VIEW_OUTPUT_HEADERS])
                self.logger.info("Couch VIEW %s" % outstring)


        #summary info
        self.logger.info("Total Doc GETs: %s" % len(gets[self.get_offset:]))
        self.logger.info("Total Doc GET time: %s ms" % (sum([x['duration'] for x in gets[self.get_offset:]])))

        self.logger.info("Total View Calls: %s" % len(views[self.view_offset:]))
        self.logger.info("Total View time: %s ms" % (sum([x['duration'] for x in views[self.view_offset:]])))

