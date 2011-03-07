from receiver.signals import form_received, successful_form_received
from datetime import datetime
import logging
import re
from corehq.apps.receiverwrapper.tasks import send_repeats
from corehq.apps.receiverwrapper.models import RepeatRecord

DOMAIN_RE = re.compile(r'^/a/(\S+)/receiver/?.*$')

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
    if matches and len(matches.groups()) == 1:
        return matches.groups()[0]
    
def add_domain(sender, xform, **kwargs):
    domain = _get_domain(xform)
    if domain: 
        xform['domain'] = domain
        xform['#export_tag'] = ["domain", "xmlns"]
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
successful_form_received.connect(send_repeaters)