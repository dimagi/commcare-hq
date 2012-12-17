from datetime import datetime, time
import tempfile
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from django_digest.decorators import httpdigest
import simplejson
from corehq.apps.api.domainapi import DomainAPI
from corehq.apps.domain.decorators import login_and_domain_required
from couchforms.models import XFormInstance
from pact.enums import PACT_DOMAIN
from django.http import Http404, HttpResponse
from casexml.apps.case.models import CommCareCase
from pact.forms.weekly_schedule_form import ScheduleForm, DAYS_OF_WEEK
from pact.models import PactPatientCase, CDotWeeklySchedule
from pact.utils import pact_script_fields, case_script_field


class PactFormAPI(DomainAPI):


    @classmethod
    def allowed_domain(self, domain):
        return PACT_DOMAIN

    @classmethod
    def api_version(cls):
        return "1"

    @classmethod
    def api_name(cls):
        return "pact_formdata"

    @httpdigest()
    def progress_note_download(self):
        """
        Download prior progress note submissions for local access
        """
        username = self.request.user.username
        if self.request.user.username == 'ctsims':
            username = 'rachel'


        offset =0
        limit_count=100
        temp_xml = tempfile.TemporaryFile()
        temp_xml.write("<restoredata>\n")
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
                                    "form.meta.username": self.request.user.username
                                }
                            }
                        ]
                    },
                    "query": {
                        "match_all": {}
                    }
                }
            },
            "size": 100,
            "fields": ['_id']
        }
        query['script_fields'] = {}
        query['script_fields'].update(pact_script_fields())
        query['script_fields'].update(case_script_field())



        #        submits_iter = XFormInstance.view('pactcarehq/progress_notes_by_chw_per_patient_date', startkey=[username, None], endkey=[username, {}], include_docs=True).iterator()
        #todo: ES based query


        #get all patients to determine which to filter.
        all_patients = PactPatient.view('pactcarehq/chw_assigned_patients', include_docs=True).all()
        #assigned_patients = PactPatient.view('pactcarehq/chw_assigned_patients', key=username, include_docs=True).all()

        active_patients = []
        for pt in all_patients:
        #if pt.arm == "Discharged":
        #continue
            pact_id = pt.pact_id
            active_patients.append(pact_id)

        for form in submits_iter:
            if form.xmlns != 'http://dev.commcarehq.org/pact/progress_note':
                continue
            if form['form']['note']['pact_id'] not in active_patients:
                continue
            xml_str = db.fetch_attachment(form['_id'], 'form.xml').replace("<?xml version=\'1.0\' ?>", '').replace("<?xml version='1.0' encoding='UTF-8' ?>", '')
            temp_xml.write(xml_str)
            temp_xml.write("\n")
            total_count += 1

            #old code, going by patient first
        #    for pact_id in active_patients:
        #        sk = [pact_id, sixmonths.year, sixmonths.month, sixmonths.day, progress_xmlns]
        #        ek = [pact_id, now.year, now.month, now.day, progress_xmlns]
        #
        #        xforms = XFormInstance.view('pactcarehq/dots_submits_by_patient_date', startkey=sk, endkey=ek, include_docs=True).all()
        #        for form in xforms:
        #            try:
        #                if form.xmlns != 'http://dev.commcarehq.org/pact/progress_note':
        #                    continue
        #                xml_str = db.fetch_attachment(form['_id'], 'form.xml').replace("<?xml version=\'1.0\' ?>", '')
        #                temp_xml.write(xml_str)
        #                temp_xml.write("\n")
        #                total_count += 1
        #            except ResourceNotFound:
        #                logging.error("Error, xform submission %s does not have a form.xml attachment." % (form._id))
        temp_xml.write("</restoredata>")
        length = temp_xml.tell()
        temp_xml.seek(0)
        wrapper = FileWrapper(temp_xml)
        response = HttpResponse(wrapper, mimetype='text/xml')
        response['Content-Length'] = length
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
