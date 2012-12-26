from datetime import datetime, time
import uuid
import dateutil
from lxml import etree
import pdb
import tempfile
from xml.etree import ElementTree
from django.core.servers.basehttp import FileWrapper
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from django_digest.decorators import httpdigest
import simplejson
from casexml.apps.case.signals import process_cases
from casexml.apps.case.tests import CaseBlock
from casexml.apps.case.xml import V2
from corehq.apps.api.domainapi import DomainAPI
from corehq.apps.api.es import XFormES, CaseES
from corehq.apps.domain.decorators import login_and_domain_required
from couchforms.models import XFormInstance
from couchforms.util import post_xform_to_couch
from dimagi.utils import make_time
from dimagi.utils.printing import print_pretty_xml
from pact.enums import PACT_DOMAIN
from django.http import Http404, HttpResponse
from casexml.apps.case.models import CommCareCase
from pact.forms.patient_form import PactPatientForm
from pact.forms.weekly_schedule_form import ScheduleForm, DAYS_OF_WEEK
from pact.models import PactPatientCase, CDotWeeklySchedule
from pact.reports import query_per_case_submissions_facet
from pact.utils import pact_script_fields, case_script_field, submit_xform


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
            "query": {
                "filtered": {
                    "filter": {
                        "and": [
                            { "term": { "domain.exact": "pact" } },
                            { "term": { "form.#type": "progress_note" } },
                            { "term": { "form.meta.username": username } }
                        ]
                    },
                    "query": { "match_all": {} }
                }
            },
            "sort": { "received_on": "asc" },
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



html_escape_table = {
    "&": "&amp;",
    '"': "&quot;",
    "'": "&apos;",
    ">": "&gt;",
    "<": "&lt;",
    }

def html_escape(text):
    """Produce entities within text."""
    return "".join(html_escape_table.get(c,c) for c in text)

def sub_element(root, tag, val):
    sube = etree.SubElement(root, tag)
    sube.text = val


def generate_meta_block(couch_user, instance_id=None, timestart=None, timeend=None):
    if timestart is None:
        timestart = datetime.utcnow()
    if timeend is None:
        timeend = datetime.utcnow()

    if instance_id is None:
        instance_id = uuid.uuid4().hex
    meta_nsmap={'n0': 'http://openrosa.org/jr/xforms', None: "http://dev.commcarehq.org/pact/patientupdate"}

    meta_lxml = etree.Element("{%s}meta" % meta_nsmap['n0'], nsmap=meta_nsmap)
    sub_element(meta_lxml, '{%s}deviceID' % meta_nsmap['n0'], 'pact_case_updater')
    sub_element(meta_lxml, '{%s}userId' % meta_nsmap['n0'], couch_user.get_id)
    sub_element(meta_lxml, '{%s}timeStart' % meta_nsmap['n0'], timestart.strftime('%Y-%m-%dT%H:%M:%SZ'))
    sub_element(meta_lxml, '{%s}timeEnd' % meta_nsmap['n0'], timeend.strftime('%Y-%m-%dT%H:%M:%SZ'))
    sub_element(meta_lxml, '{%s}instanceID' % meta_nsmap['n0'], instance_id)
    return meta_lxml


def prepare_case_update_xml_block(casedoc, couch_user, update_dict, submit_date):
    case_nsmap = {'n1': 'http://commcarehq.org/case/transaction/v2'}
    def make_update(update_elem, updates):
        for k,v in updates.items():
            if v is not None:
                sub_element(update_elem, '{%(ns)s}%(tag)s' % {'ns': case_nsmap['n1'], 'tag': k}, v)

    case_lxml = etree.Element('{%s}case' % case_nsmap['n1'], nsmap=case_nsmap, case_id=casedoc._id, user_id=couch_user._id, date_modified=submit_date.strftime("%Y-%m-%dT%H:%M:%SZ"))
    update_lxml = etree.SubElement(case_lxml, '{%s}update' % case_nsmap['n1'])
    make_update(update_lxml, update_dict)
    return case_lxml


def recompute_dots_update(casedoc, submit_date=None):
    """
    On a DOT submission, recompute the DOT block and submit a case update xform
    """

    pass

def submit_case_update_form(casedoc, update_dict, couch_user, submit_date=None):
    """
    Main entry point for submitting an update for a pact patient

    Args:
    casedoc: the patient case
    update_dict: the kv of the fields being changed
    couch_user: user committing the change
    submit_date: now if None
    """

    if submit_date is None:
        submit_date = datetime.utcnow()
    form = etree.Element("data", nsmap={None: "http://dev.commcarehq.org/pact/patientupdate", 'jrm': "http://dev.commcarehq.org/jr/xforms"})

    meta_block = generate_meta_block(couch_user, timestart=submit_date, timeend=submit_date)
    form.append(meta_block)
    #    if include_dots:
#        update_dict.update(case_doc.calculate_regimen_caseblock())
#        dots_data = case_doc.get_dots_data()
#        update_dict['dots'] =  simplejson.dumps(dots_data)

#    caseblock = CaseBlock(casedoc._id, update=update_dict, close=False, date_modified=submit_date.strftime("%Y-%m-%dT%H:%M:%SZ"), version=V2)
#    print caseblock.as_xml(format_datetime=isodate_string)
    update_block = prepare_case_update_xml_block(casedoc, couch_user, update_dict, submit_date)
    form.append(update_block)

    print etree.tostring(form, pretty_print=True)
    submission_xml_string = etree.tostring(form)
    submit_xform('/a/pact/receiver', PACT_DOMAIN, submission_xml_string)


def isodate_string(date):
    if date: return dateutil.datetime_isoformat(date) + "Z"
    return ""





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
        if self.method == "rm_schedule":
            if self.request.POST.has_key('rm_schedule'):
                #hacky remove schedule method
                pdoc.rm_schedule()
                resp.status_code = 204
                return resp

        elif self.method == "schedule":
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
        elif self.method == "patient_edit":
            form = PactPatientForm(pdoc, data=self.request.POST)
            if form.is_valid():
                update_data = form.clean_changed_data
                submit_case_update_form(pdoc, update_data, self.request.couch_user)
                resp.status_code = 204
                return resp
            else:
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
