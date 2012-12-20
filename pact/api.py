from datetime import datetime, time
import tempfile
from django.core.servers.basehttp import FileWrapper
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from django_digest.decorators import httpdigest
import simplejson
from corehq.apps.api.domainapi import DomainAPI
from corehq.apps.api.es import XFormES, CaseES
from corehq.apps.domain.decorators import login_and_domain_required
from couchforms.models import XFormInstance
from pact.enums import PACT_DOMAIN
from django.http import Http404, HttpResponse
from casexml.apps.case.models import CommCareCase
from pact.forms.weekly_schedule_form import ScheduleForm, DAYS_OF_WEEK
from pact.models import PactPatientCase, CDotWeeklySchedule
from pact.reports import query_per_case_submissions_facet
from pact.utils import pact_script_fields, case_script_field


class PactFormAPI(DomainAPI):

    xform_es = XFormES()
    case_es = CaseES()

    @classmethod
    def allowed_domain(self, domain):
        return PACT_DOMAIN

    @classmethod
    def api_version(cls):
        return "1"

    @classmethod
    def api_name(cls):
        return "pact_formdata"

#    @method_decorator(login_and_domain_required)
    def dispatch(self, *args, **kwargs):
        req = args[0]
        if not self.allowed_domain(req.domain):
            raise Http404
        ret =  super(PactFormAPI, self).dispatch(*args, **kwargs)
        return ret

    @httpdigest()
#    def progress_note_download(self):
    def get(self, *args, **kwargs):
        """
        Download prior progress note submissions for local access
        """

        db = XFormInstance.get_db()
        username = self.request.user.username
        if self.request.user.username == 'ctsims':
            username = 'rachel'
        username='cs783'

        offset =0
        limit_count=200
        total_count = 0

        query = {
            "sort": {
                "received_on": "asc"
            },
            "query": {
                "filtered": {
                    "filter": {
                        "and": [
                            {
                                "term": {
                                    "domain.exact": "pact"
                                }
                            },
                            {
                                "term": {
                                    "form.#type": "progress_note"
                                }
                            },
                            {
                                "term": {
                                    "form.meta.username": username
                                }
                            }
                        ]
                    },
                    "query": {
                        "match_all": {}
                    }
                }
            },
            "size": limit_count,
            "fields": ['_id']
        }
        query['script_fields'] = {}
        query['script_fields'].update(pact_script_fields())
        query['script_fields'].update(case_script_field())

        res = self.xform_es.run_query(query)


        my_patients_ever_submitted_query = query_per_case_submissions_facet(PACT_DOMAIN, username)
        patients_res = self.xform_es.run_query(my_patients_ever_submitted_query)

        #filter by active/discharged?
        #get all the forms
        #get all the patients
        #get all patients to determine which to filter.

        active_patients = []
        for pt in []:
            #if pt.hp_status == "Discharged":
                #continue
            case_id = pt['script_case_id']
            active_patients.append(case_id)

        def return_iterator():
            yield "<restoredata>"
            for result in res['hits']['hits']:
                data_row = result['fields']

#                if data_row['script_case_id'] not in active_patients:
#                    continue
                try:
                    xml_str = db.fetch_attachment(data_row['_id'], 'form.xml').replace("<?xml version=\'1.0\' ?>", '').replace("<?xml version='1.0' encoding='UTF-8' ?>", '')
                    yield xml_str
                except Exception, ex:
                    print "error fetching attachment: %s" % ex

            yield "</restoredata>"


        def return_tmpfile():
            temp_xml = tempfile.TemporaryFile()
#        temp_xml.write("<restoredata>\n")
#        temp_xml.write("</restoredata>")
            length = temp_xml.tell()
            temp_xml.seek(0)
            wrapper = FileWrapper(temp_xml)
            response = HttpResponse(wrapper, mimetype='text/xml')
            response['Content-Length'] = length

        response = HttpResponse(return_iterator(), mimetype='text/xml')
        return response

class PactAPI(DomainAPI):

    #note - for security purposes, csrf protection is ENABLED
    #search POST queries must take the following format:
    #query={query_json}
    #csrfmiddlewaretoken=token

    #in curl, this is:
    #curl -b "csrftoken=<csrftoken>;sessionid=<session_id>" -H "Content-Type: application/json" -XPOST http://server/a/domain/api/v0.1/xform_es/
    #     -d"query=@myquery.json&csrfmiddlewaretoken=<csrftoken>"

    @classmethod
    def allowed_domain(self, domain):
        return PACT_DOMAIN

    @classmethod
    def api_version(cls):
        return "1"

    @classmethod
    def api_name(cls):
        return "pactdata"

    http_method_names = ['get', 'post', 'head', ]

    def get(self, *args, **kwargs):
        print "\tget"
        if self.request.GET.get('case_id', None) is None:
            raise Http404

        case = PactPatientCase.get(self.request.GET['case_id'])
        if self.method is None:
            return HttpResponse("API Method unknown: no method", status=400)
        elif self.method == "schedule":
            scheds = case.get_schedules(raw_json=True)

            payload = simplejson.dumps(scheds)
            response = HttpResponse(payload, content_type="application/json")
            return response
        else:
            return HttpResponse("API Method unknown", status=400)

    def post(self,  *args, **kwargs):
        pdoc = PactPatientCase.get(self.request.GET['case_id'])
        resp = HttpResponse()
        if self.method is not None:
            if self.request.POST.has_key('rm_schedule'):
                #hacky remove schedule method
                pdoc.rm_schedule()
                resp.status_code = 204
                return resp



            form = ScheduleForm(data=self.request.POST)

            if form.is_valid():
                sched = CDotWeeklySchedule()
                for day in DAYS_OF_WEEK:
                    if form.cleaned_data[day] != 'None':
                        setattr(sched, day, form.cleaned_data[day])
                if form.cleaned_data['active_date'] == None:
                    sched.started = datetime.utcnow()
                else:
                    sched.started = datetime.combine(form.cleaned_data['active_date'], time.min)
                sched.comment = form.cleaned_data['comment']
                sched.created_by = self.request.user.username
                sched.deprecated = False
                pdoc.set_schedule(sched)
                resp.status_code = 204
                return resp
            else:
                print form.errors
                resp.write(str(form.errors))
                resp.status_code = 406
                return resp

    def head(self, *args, **kwargs):
        raise NotImplementedError("Not implemented")


    @method_decorator(login_and_domain_required)
#    @method_decorator(csrf_protect)
    def dispatch(self, *args, **kwargs):
        req = args[0]
        self.method = req.GET.get('method', None)
        ret =  super(PactAPI, self).dispatch(*args, **kwargs)
        return ret
