from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import datetime, time
import logging
import uuid

from lxml import etree
from django.utils.decorators import method_decorator
from casexml.apps.phone.middleware import LAST_SYNCTOKEN_HEADER
from dimagi.utils.parsing import json_format_date
from django_digest.decorators import httpdigest
import json
from django.http import Http404, HttpResponse
from django.core.cache import cache

from corehq.apps.api.domainapi import DomainAPI
from corehq.apps.api.es import ReportXFormES
from corehq.apps.domain.decorators import login_or_digest
from corehq.apps.fixtures.models import FixtureDataItem
from corehq.apps.groups.models import Group
from corehq.apps.users.models import CouchUser
from corehq.blobs.mixin import BlobHelper, CODES
from couchforms.models import XFormInstance
import localsettings
from pact.dot_data import get_dots_case_json
from pact.enums import (PACT_DOMAIN, XMLNS_PATIENT_UPDATE, PACT_HP_GROUPNAME, PACT_PROVIDERS_FIXTURE_CACHE_KEY,
                        XMLNS_PATIENT_UPDATE_DOT)
from pact.forms.patient_form import PactPatientForm
from pact.forms.weekly_schedule_form import ScheduleForm, DAYS_OF_WEEK
from pact.tasks import set_schedule_case_properties
from pact.utils import pact_script_fields, case_script_field, submit_xform, query_per_case_submissions_facet
from corehq.apps.app_manager.dbaccessors import get_latest_build_id
from six.moves import range

PACT_CLOUD_APPNAME = "PACT Cloud"
PACT_CLOUDCARE_MODULE = "PACT Cloudcare"

FORM_PROGRESS_NOTE = "Progress Note"
FORM_DOT = "DOT Form"
FORM_BLOODWORK = "Bloodwork"
FORM_ADDRESS = "Address and Phone Update"


def get_cloudcare_app():
    """
    Total hack function to get direct links to the cloud care application pages
    """

    from corehq.apps.cloudcare import api

    app = api.get_cloudcare_app(PACT_DOMAIN, PACT_CLOUD_APPNAME)
    app_id = app['_id']

    pact_cloudcare = [x for x in app['modules'] if x['name']['en'] == PACT_CLOUDCARE_MODULE]
    forms = pact_cloudcare[0]['forms']
    ret = dict((f['name']['en'], ix) for (ix, f) in enumerate(forms))

    ret['app_id'] = app_id
    ret['build_id'] = get_latest_build_id(PACT_DOMAIN, app_id)
    return ret


def get_cloudcare_url(case_id, mode):
    from corehq.apps.cloudcare.utils import webapps_module_form_case

    app_dict = get_cloudcare_app()
    build_id = app_dict['build_id']
    return webapps_module_form_case(
        PACT_DOMAIN, app_id=build_id, module_id=0, form_id=app_dict[mode], case_id=case_id)


class PactFormAPI(DomainAPI):
    xform_es = ReportXFormES(PACT_DOMAIN)

    @classmethod
    def allowed_domain(self, domain):
        return PACT_DOMAIN

    @classmethod
    def api_version(cls):
        return "1"

    @classmethod
    def api_name(cls):
        return "pact_formdata"

    @method_decorator(httpdigest)
    @method_decorator(login_or_digest)
    def get(self, *args, **kwargs):
        """
        Download prior progress note submissions for local access
        """
        db = XFormInstance.get_db()
        couch_user = CouchUser.from_django_user(self.request.user)
        username = couch_user.raw_username
        if hasattr(localsettings, 'debug_pact_user'):
            username = getattr(localsettings, 'debug_pact_user')(username)

        offset =0
        limit_count=200
        total_count = 0

        query = {
            "query": {
                "filtered": {
                    "filter": {
                        "and": [
                            {"term": {"domain.exact": "pact"}},
                            {"term": {"form.#type": "progress_note"}},
                            {"term": {"form.meta.username": username}}
                        ]
                    },
                    "query": {"match_all": {}}
                }
            },
            "sort": {"received_on": "asc"},
            "size": limit_count,
            "fields": ['_id', 'external_blobs']
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
                    xml_str = (BlobHelper(data_row, db, CODES.form_xml)
                        .fetch_attachment('form.xml').decode('utf-8')
                        .replace("<?xml version=\'1.0\' ?>", '')
                        .replace("<?xml version='1.0' encoding='UTF-8' ?>", ''))
                    yield xml_str
                except Exception as ex:
                    logging.error("for downloader: error fetching attachment: %s" % ex)
            yield "</restoredata>"

        response = HttpResponse(return_iterator(), content_type='text/xml')
        return response


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
    meta_nsmap={'n0': 'http://openrosa.org/jr/xforms' }

    meta_lxml = etree.Element("{%s}meta" % meta_nsmap['n0'], nsmap=meta_nsmap)
    sub_element(meta_lxml, '{%s}deviceID' % meta_nsmap['n0'], 'pact_case_updater')
    sub_element(meta_lxml, '{%s}userID' % meta_nsmap['n0'], couch_user.get_id)
    sub_element(meta_lxml, '{%s}timeStart' % meta_nsmap['n0'], timestart.strftime('%Y-%m-%dT%H:%M:%SZ'))
    sub_element(meta_lxml, '{%s}timeEnd' % meta_nsmap['n0'], timeend.strftime('%Y-%m-%dT%H:%M:%SZ'))
    sub_element(meta_lxml, '{%s}instanceID' % meta_nsmap['n0'], instance_id)
    return meta_lxml


def prepare_case_update_xml_block(casedoc, couch_user, update_dict, submit_date):
    case_nsmap = {'n1': 'http://commcarehq.org/case/transaction/v2'}

    def make_update(update_elem, updates):
        for k, v in updates.items():
            if v is not None:
                sub_element(update_elem, '{%(ns)s}%(tag)s' % {'ns': case_nsmap['n1'], 'tag': k}, v)

    case_lxml = etree.Element('{%s}case' % case_nsmap['n1'], nsmap=case_nsmap, case_id=casedoc._id, user_id=couch_user._id, date_modified=submit_date.strftime("%Y-%m-%dT%H:%M:%SZ"))
    update_lxml = etree.SubElement(case_lxml, '{%s}update' % case_nsmap['n1'])
    make_update(update_lxml, update_dict)

    return case_lxml


def recompute_dots_casedata(casedoc, couch_user, submit_date=None, sync_token=None):
    """
    On a DOT submission, recompute the DOT block and submit a casedoc update xform
    Recompute and reset the ART regimen and NONART regimen to whatever the server says it is, in the casedoc where there's an idiosyncracy with how the phone has it set.

    This only updates the patient's casexml block with new dots data, and has no bearing on website display - whatever is pulled from the dots view is real.
    """
    if getattr(casedoc, 'dot_status', None) in ['DOT5', 'DOT3', 'DOT1']:
        update_dict = {}
        dots_data = get_dots_case_json(casedoc)

        update_dict['dots'] = json.dumps(dots_data)
        submit_case_update_form(casedoc, update_dict, couch_user, submit_date=submit_date, xmlns=XMLNS_PATIENT_UPDATE_DOT, sync_token=sync_token)


def submit_case_update_form(casedoc, update_dict, couch_user, submit_date=None, xmlns=XMLNS_PATIENT_UPDATE, sync_token=None):
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
    form = etree.Element("data", nsmap={None: xmlns, 'jrm': "http://dev.commcarehq.org/jr/xforms"})
    meta_block = generate_meta_block(couch_user, timestart=submit_date, timeend=submit_date)
    form.append(meta_block)

    update_block = prepare_case_update_xml_block(casedoc, couch_user, update_dict, submit_date)
    form.append(update_block)
    # todo: this date is based off midnight UTC not local time...
    encounter_date = etree.XML('<encounter_date>%s</encounter_date>' % json_format_date(datetime.utcnow()))
    form.append(encounter_date)

    submission_xml_string = etree.tostring(form).decode('utf-8')
    if sync_token:
        extra_meta = {LAST_SYNCTOKEN_HEADER: sync_token}
    else:
        extra_meta = None
    return submit_xform('/a/pact/receiver', PACT_DOMAIN, submission_xml_string, extra_meta=extra_meta)


def get_all_providers(invalidate=False):
    """
    wrapper function to get all the providers for PACT and cache them.
    ugly for now - the number of entries is small enough that loading all and scanning on checking is small enough overhead on a single page load.
    """
    if invalidate:
        cache.delete(PACT_PROVIDERS_FIXTURE_CACHE_KEY)
    raw_cached_fixtures = cache.get(PACT_PROVIDERS_FIXTURE_CACHE_KEY, None)
    if raw_cached_fixtures is None:
        #requery and cache
        pact_hp_group = Group.by_name(PACT_DOMAIN, PACT_HP_GROUPNAME)
        providers = FixtureDataItem.by_group(pact_hp_group)
        cache.set(PACT_PROVIDERS_FIXTURE_CACHE_KEY, json.dumps([x.to_json() for x in providers]))
        return providers
    else:
        try:
            json_data = json.loads(raw_cached_fixtures)
            #not necessary in the grand scheme of things - we could really just use raw JSON
            return [FixtureDataItem.wrap(x) for x in json_data]
        except Exception as ex:
            logging.error("Error loading json from cache key %s: %s" % (PACT_PROVIDERS_FIXTURE_CACHE_KEY, ex))
            return []

#    cache.set('%s_casedoc' % self._id, json.dumps(self._case), PACT_CACHE_TIMEOUT)
#        xml_ret = cache.get('%s_schedule_xml' % self._id, None)
        pass


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
        from pact.models import PactPatientCase

        if self.request.GET.get('case_id', None) is None:
            raise Http404

        case = PactPatientCase.get(self.request.GET['case_id'])
        if self.method is None:
            return HttpResponse("API Method unknown: no method", status=400)
        elif self.method == "schedule":
            scheds = case.get_schedules(raw_json=True)
            if scheds is None:
                scheds = []

            payload = json.dumps(scheds)
            response = HttpResponse(payload, content_type="application/json")
            return response
        elif self.method == 'providers':
            providers = get_all_providers()
            providers = sorted(providers, key=lambda x: x.fields_without_attributes['last_name'])
            providers_by_id = dict(
                (x.fields_without_attributes['id'], x.fields_without_attributes)
                for x in providers
            )
            case_providers = [providers_by_id.get(x, None) for x in case.get_provider_ids()]
            facilities = set()
            for prov in providers:
                facility = prov.fields_without_attributes['facility_name']
                if facility is None:
                    facility = 'N/A'
                facilities.add(facility)
            ret = {
                'facilities': ['All Facilities'] + sorted(list(facilities)),
                "providers": [x.fields_without_attributes for x in providers],
                "case_providers": case_providers,
            }
            resp = HttpResponse(json.dumps(ret), content_type='application/json')
            return resp
        else:
            return HttpResponse("API Method unknown", status=400)

    def post(self,  *args, **kwargs):
        from pact.models import PactPatientCase, CDotWeeklySchedule

        pdoc = PactPatientCase.get(self.request.GET['case_id'])
        resp = HttpResponse()
        if self.method == "rm_schedule":
            if 'rm_schedule' in self.request.POST:
                #hacky remove schedule method
                pdoc.rm_last_schedule()
                pdoc.save()
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
                pdoc.save()
                set_schedule_case_properties(pdoc)
                resp.status_code = 204
                return resp
            else:
                resp.write(str(form.errors))
                resp.status_code = 406
                return resp

        elif self.method == 'providers':
            try:
                submitted_provider_ids = json.loads(self.request.POST['selected_providers'])
                case_provider_ids = list(pdoc.get_provider_ids())

                if submitted_provider_ids != case_provider_ids:
                    try:
                        #len difference
                        submitted_len = len(submitted_provider_ids)
                        case_len = len(case_provider_ids)
                        if submitted_len < case_len:
                            for x in range(case_len-submitted_len):
                                submitted_provider_ids.append('')
                        pdoc.update_providers(self.request.couch_user, submitted_provider_ids)
                        resp.write("success")
                        resp.status_code=204
                    except Exception as ex:
                        resp.write("Error submitting: %s" % ex)
                        resp.status_code=500
                else:
                    resp.write("")
                    resp.status_code=304
            except Exception as ex:
                resp.write("Error submitting: %s" % ex)
                resp.status_code=500
            return resp

        elif self.method == "patient_edit":
            form = PactPatientForm(self.request, pdoc, data=self.request.POST)
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

    @method_decorator(login_or_digest)
    def dispatch(self, *args, **kwargs):
        req = args[0]
        self.method = req.GET.get('method', None)
        ret = super(PactAPI, self).dispatch(*args, **kwargs)
        return ret
