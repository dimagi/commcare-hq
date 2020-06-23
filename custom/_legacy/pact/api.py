from datetime import datetime, time
import logging
import uuid

from lxml import etree
from casexml.apps.phone.middleware import LAST_SYNCTOKEN_HEADER
from dimagi.utils.parsing import json_format_date
import json
from django.core.cache import cache

from corehq.apps.fixtures.models import FixtureDataItem
from corehq.apps.groups.models import Group
from pact.dot_data import get_dots_case_json
from pact.enums import (PACT_DOMAIN, XMLNS_PATIENT_UPDATE, PACT_HP_GROUPNAME, PACT_PROVIDERS_FIXTURE_CACHE_KEY,
                        XMLNS_PATIENT_UPDATE_DOT)
from pact.utils import submit_xform
from corehq.apps.app_manager.dbaccessors import get_latest_build_id

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

