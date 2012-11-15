from django.core.management.base import NoArgsCommand
from django.test.client import RequestFactory
from openpyxl.worksheet import Worksheet
import os
import simplejson
from corehq.apps.fixtures.views import UploadItemLists
from pact.management.commands import PactMigrateCommand
from pact.management.commands.constants import  PACT_URL, PACT_DOMAIN
from openpyxl.workbook import Workbook
import tempfile

exclude_fields = ['_id', 'username', 'user_id', 'case_id_map', '_rev', 'actor_uuid', 'doc_type',
                  'new_user', 'base_type']
class Command(PactMigrateCommand):
    help = "Create or update pact users from django to WebUsers"
    option_list = NoArgsCommand.option_list + (
    )

    def handle_noargs(self, **options):
        self.get_credentials()
        print "#### Getting actors json from server"
        actors_json = simplejson.loads(self.get_url(PACT_URL + 'hqmigration/actors/'))

        fields = set()
        rows = []
        wb = Workbook()
        title_ws = wb.get_active_sheet()
        title_ws.title = 'types'
        for actor in actors_json:
            #for the actors now, walk their properties and add them to the WebUser
            if actor['doc_type'] == 'ProviderActor':
                actor_fields = filter(lambda x: x not in exclude_fields, actor.keys())
                fields.update(actor_fields)
                #print actor
        print "providers loaded, preparing data"

        #write the types sheet
        #name, tag, field n...
        title_ws.append(['name', 'tag',] + ['field %d' % x for x in range(len(fields))])
        title_ws.append(['Pact Provider', 'provider'] + [x for x in fields])

        #write data
        data_ws = wb.create_sheet()
        data_ws.title = 'provider'
        data_ws.append(['field:%s'% x for x in fields])
        for actor in actors_json:
            if actor['doc_type'] == 'ProviderActor':
                data_ws.append([actor.get(field, None) for field in fields])
        print "providers loaded into excel file, uploading"

        f, fname = tempfile.mkstemp(suffix='.xlsx')
        wb.save(fname)
        print fname
        #alskdjf
        print "providers uploaded to fixture"

        with open(fname, 'rb') as fin:
            rf = RequestFactory()
            req = rf.post('/a/pact/receiver', data={ 'file': fin }) #,
            # content_type='multipart/form-data')
            ul = UploadItemLists()
            ul.domain = PACT_DOMAIN
            print ul.post(req)
        os.remove(fname)





