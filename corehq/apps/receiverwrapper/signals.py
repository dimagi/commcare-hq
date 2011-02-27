from receiver.signals import form_received
import logging
import re

DOMAIN_RE = re.compile(r'^/a/(\w+)/receiver/?.*$')

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
            
def add_domain(sender, xform, **kwargs):
    matches = DOMAIN_RE.search(xform.path)
    if matches and len(matches.groups()) == 1:
        domain = matches.groups()[0]
        xform['domain'] = domain
        xform['#export_tag'] = ["domain", "xmlns"]
        xform.save()

form_received.connect(scrub_meta)
form_received.connect(add_domain)
