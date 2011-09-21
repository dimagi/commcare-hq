from corehq.apps.domain.utils import normalize_domain_name
from receiver.signals import form_received, successful_form_received
from datetime import datetime
import logging
import re
from corehq.apps.receiverwrapper.tasks import send_repeats
from corehq.apps.receiverwrapper.models import RepeatRecord
import types

DOMAIN_RE = re.compile(r'^/a/(\S+)/receiver(/(.*))?/?$')
APP_ID_RE = re.compile(r'^/a/\S+/receiver/(.*)/$')

def scrub_meta(sender, xform, **kwargs):
    property_map = {"TimeStart": "timeStart",
                    "TimeEnd": "timeEnd",
                    "chw_id": "userID",
                    "DeviceID": "deviceID",
                    "uid": "instanceID"}

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
    if found_old:
        logging.error("form %s contains old-format metadata.  You should update it!!" % xform.get_id)
        xform.save()
            
def _get_domain(xform):
    matches = DOMAIN_RE.search(xform.path)
    if matches and len(matches.groups()):
        return normalize_domain_name(matches.groups()[0])

def _get_app_id(xform):
    matches = APP_ID_RE.search(xform.path)
    if matches and len(matches.groups()) and matches.groups()[0]:
        return matches.groups()[0]

def add_domain(sender, xform, **kwargs):
    domain = _get_domain(xform)
    if domain: 
        xform['domain'] = domain
        xform['#export_tag'] = ["domain", "xmlns"]
        xform.save()

def add_app_id(sender, xform, **kwargs):
    app_id = _get_app_id(xform)
    if app_id:
        xform['app_id'] = app_id
        xform.save()

def send_repeaters(sender, xform, **kwargs):
    from corehq.apps.receiverwrapper.models import FormRepeater
    domain = _get_domain(xform)
    if domain:
        repeaters = FormRepeater.view("receiverwrapper/repeaters", key=domain, include_docs=True).all()
        # tag the repeat_to field an save first. if we crash between here and 
        # when we do the actual repetition this will be preserved
        if repeaters:
            xform["repeats"] = [RepeatRecord(url=repeater.url, next_check=datetime.utcnow()).to_json() for repeater in repeaters]
            xform.save()
            send_repeats.delay(xform.get_id)
                
        
form_received.connect(scrub_meta)
form_received.connect(add_domain)
form_received.connect(add_app_id)
successful_form_received.connect(send_repeaters)