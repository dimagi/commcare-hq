from django.core.management.base import NoArgsCommand
from django.test.client import RequestFactory
import os
import simplejson
import sys
from casexml.apps.case.models import CommCareCase
from corehq.apps.fixtures.views import UploadItemLists
from corehq.apps.users.models import CommCareUser
from couchforms.models import XFormInstance
from pact.api import submit_case_update_form
from pact.management.commands import PactMigrateCommand
from pact.management.commands.constants import PACT_URL
from pact.enums import PACT_DOMAIN, PACT_HP_GROUPNAME
from openpyxl.workbook import Workbook
import tempfile
from pact.models import PactPatientCase

exclude_fields = ['username', 'user_id', 'case_id_map', '_rev', 'actor_uuid', 'doc_type', 'new_user', 'base_type', 'name','title','affiliation']
exclude_docs = ['e13a2696f84e4c089a038934dfd41387', '9cc7be3f10584b0bb3d6978ae012f4cc']
class Command(PactMigrateCommand):
    help = "Create or update pact users from django to WebUsers"
    option_list = NoArgsCommand.option_list + (
    )

    def handle_noargs(self, **options):
        self.get_credentials()
        #purge items
        db = XFormInstance.get_db()
        items = db.view('fixtures/ownership', include_docs=True, reduce=False, startkey=['group by data_item', PACT_DOMAIN], endkey=['group by data_item', PACT_DOMAIN, {}]).all()
        for d in items:
            print "deleting %s" % d
            db.delete_doc(d['doc'])

        case_provider_map = {}

        print "#### Getting actors json from server"
        actors_json = simplejson.loads(self.get_url(PACT_URL + 'hqmigration/actors/'))

        field_headings = [
                          'field:id',
                          'field:first_name',
                          'field:last_name',
                          'field:role',
                          'field:email',
                          'field:facility_name',
                          'field:facility_address',
                          'field:phone_number',
                          'field:notes'
                        ]
        ordered_fields = ['_id', 'first_name', 'last_name', 'provider_title', 'email', 'facility_name', 'facility_address', 'phone_number', 'notes']
        display_fields = ['id', 'first_name', 'last_name', 'role', 'email', 'facility_name', 'facility_address', 'phone_number', 'notes']

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


#        for case, actors in case_provider_map.items():
#            print "%s: %s" % (case, actors)
        print fields
        print "providers loaded, preparing data"

        #write the types sheet
        #name, tag, field n...
        title_ws.append(['name', 'tag',] + ['field %d' % x for x in range(len(display_fields))])
        title_ws.append(['Pact Provider', 'provider'] + [x for x in display_fields])

        #write data
        data_ws = wb.create_sheet()
        data_ws.title = 'provider'

        #err, just make it ordered
        #field_headings = ['field:%s'% x for x in fields]
#        field_headings = []
#        for x in fields:
#            print "#%s#" % x
#            if x == '_id':
#                rawfield = 'id'
#            elif x == 'provide/r_title':
#                rawfield = "role"
#            else:
#                rawfield = x
#            print rawfield
#            field_heading_text = "field:%s" % rawfield
#            field_headings.append(field_heading_text)

        data_ws.append(field_headings + ['group 1'])
        #fill actual provider data
        for actor in actors_json:
            if actor['doc_type'] == 'ProviderActor':
                datarow = [actor.get(field, None) for field in ordered_fields] + [PACT_HP_GROUPNAME]
#                print datarow
                if datarow[0] in exclude_docs:
                    continue
                data_ws.append(datarow)
                cases = actor['case_id_map']
                for case in cases:
                    case_id = case[1]
                    if not case_provider_map.has_key(case_id):
                        case_provider_map[case_id] = []
                    case_provider_map[case_id].append(datarow)



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
            posted=ul.post(req)
#        os.remove(fname)
        #todo: post xform indicating affiliation
            #case_provider_map[case_id].append("%s %s: %s" % (actor['first_name'], actor['last_name'], actor['email']))

        cc_user = CommCareUser.get_by_username('pactimporter@pact.commcarehq.org')
        for case_id, providers_arr in case_provider_map.items():

            prov_ids = [x[0] for x in providers_arr]
            casedoc = PactPatientCase.get(case_id)
            casedoc.update_providers(cc_user, prov_ids)

