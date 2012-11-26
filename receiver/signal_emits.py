# These are traditional signals that are emitted
import logging
import types
from receiver.signals import form_received


def scrub_meta(sender, xform, **kwargs):
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
                logging.error(
                    "form %s contains multiple meta blocks. this is not correct but we picked one abitrarily" % xform.get_id)
            else:
                # if it's a list of something other than dictionaries.
                # don't bother scrubbing.
                logging.error(
                    "form %s contains a poorly structured meta block. this might cause data display problems.")
        if isinstance(xform.form["meta"], dict):
            for key in xform.form["meta"]:
                if key in property_map and property_map[key] not in xform.form["meta"]:
                    xform.form["meta"][property_map[key]] = xform.form["meta"][key]
                    del xform.form["meta"][key]
                    found_old = True
    if found_old:
        xform.save()

form_received.connect(scrub_meta)
