from casexml.apps.case.signals import case_post_save
from corehq.apps.domain.utils import normalize_domain_name
from receiver.signals import form_received, successful_form_received
import logging
import re
import types
from couchforms.signals import submission_error_received

DOMAIN_RE = re.compile(r'^/a/(\S+)/receiver(/(.*))?/?$')
# app id has to be at least 10 characters long.
# This indirectly keeps 'secure' itself from being interpreted as the app id
APP_ID_RE = re.compile(r'^/a/\S+/receiver/(?:secure/)?(.{10,})/$')


def scrub_meta(sender, xform):
    """
    Cleans up old format metadata to our current standard.

    Does NOT save the doc, but returns whether the doc needs to be saved.
    """
    property_map = {"TimeStart": "timeStart",
                    "TimeEnd": "timeEnd",
                    "chw_id": "userID",
                    "DeviceID": "deviceID",
                    "uid": "instanceID"}

    if not hasattr(xform, "form"):
        return
    
    # hack to make sure uppercase meta still ends up in the right place
    found_old = False
    if "Meta" in xform.form:
        xform.form["meta"] = xform.form["Meta"]
        del xform.form["Meta"]
        found_old = True
    if "meta" in xform.form:
        # scrub values from 0.9 to 1.0
        if isinstance(xform.form["meta"], types.ListType):
            if isinstance(xform.form["meta"][0], types.DictionaryType):
                # if it's a list of dictionaries, arbitrarily pick the first 
                # one. this is a pretty serious error, but it's also recoverable.
                xform.form["meta"] = xform.form["meta"][0]
                logging.error("form %s contains multiple meta blocks. this is not correct but we picked one abitrarily" % xform.get_id)
            else:
                # if it's a list of something other than dictionaries. 
                # don't bother scrubbing. 
                logging.error("form %s contains a poorly structured meta block. this might cause data display problems.")
        if isinstance(xform.form["meta"], dict):
            for key in xform.form["meta"]:
                if key in property_map and property_map[key] not in xform.form["meta"]:
                    xform.form["meta"][property_map[key]] = xform.form["meta"][key]
                    del xform.form["meta"][key]
                    found_old = True

    return found_old


def _get_domain(xform):
    matches = DOMAIN_RE.search(xform.path)
    if matches and len(matches.groups()):
        return normalize_domain_name(matches.groups()[0])


def _get_app_id(xform):
    matches = APP_ID_RE.search(xform.path)
    if matches and len(matches.groups()) and matches.groups()[0]:
        return matches.groups()[0]


def add_domain(sender, xform, **kwargs):
    domain = _get_domain(xform) or ""
    to_update = domain != xform._doc.get('domain', None)
    xform.domain = domain
    return to_update


def add_export_tag(sender, xform):
    if _get_domain(xform):
        xform['#export_tag'] = ["domain", "xmlns"]
        return True


def add_app_id(sender, xform):
    app_id = _get_app_id(xform)
    if app_id:
        xform['app_id'] = app_id
        return True


def create_form_repeat_records(sender, xform, **kwargs):
    from corehq.apps.receiverwrapper.models import FormRepeater
    xform.domain = _get_domain(xform)
    create_repeat_records(FormRepeater, xform)



def create_case_repeat_records(sender, case, **kwargs):
    from corehq.apps.receiverwrapper.models import CaseRepeater
    create_repeat_records(CaseRepeater, case)


def create_short_form_repeat_records(sender, xform, **kwargs):
    from corehq.apps.receiverwrapper.models import ShortFormRepeater
    xform.domain = _get_domain(xform)
    create_repeat_records(ShortFormRepeater, xform)


def create_repeat_records(repeater_cls, payload):
    domain = payload.domain
    if domain:
        repeaters = repeater_cls.by_domain(domain)
        for repeater in repeaters:
            repeater.register(payload)


def form_processing(sender, xform, **kwargs):
    should_update = scrub_meta(sender, xform)
    should_update = add_domain(sender, xform) or should_update
    should_update = add_export_tag(sender, xform) or should_update
    should_update = add_app_id(sender, xform) or should_update
    # form received saves the doc right after calling this signal,
    # so we don't have to save, though would need to here if that changes
    return should_update


def error_processing(sender, xform, **kwargs):
    should_update = add_domain(sender, xform)
    should_update = add_app_id(sender, xform) or should_update
    return should_update


form_received.connect(form_processing)
submission_error_received.connect(error_processing)

successful_form_received.connect(create_form_repeat_records)
successful_form_received.connect(create_short_form_repeat_records)
case_post_save.connect(create_case_repeat_records)
