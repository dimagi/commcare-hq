'''
Created on Nov 30, 2011

@author: czue
'''
from dimagi.utils.data.generator import random_phonenumber, random_fullname,\
    random_lastname, random_username
from lxml import etree
import random
from couchforms.models import XFormInstance

def random_momage():
    return random.randint(14, 55)

CRS_REGISTRATION = "http://openrosa.org/formdesigner/393CC825-7874-40E7-9AC6-927B09E832EC"
CRS_CHECKLIST = "http://openrosa.org/formdesigner/51283B9F-F810-44C9-8BCE-0A170F917BC1"
CRS_BIRTH = "http://openrosa.org/formdesigner/B3CEEEFF-0673-4AAF-8A77-AC6C0DB68ADD"

FORM_CONFIG = { CRS_REGISTRATION: {
                    "full_name": random_fullname,
                    "age": random_momage,
                    "number": random_phonenumber,
                    "husband_name": random_fullname,
                    "hamlet_name": random_lastname,
                    "case/create/case_name": random_fullname, 
                    "case/update/husband_name": random_fullname,
                    "meta/username": random_username },
                CRS_CHECKLIST: {
                    "client_name": random_fullname,
                    "meta/username": random_username },
                CRS_BIRTH: {
                    "meta/username": random_username }
              }
    
def deidentify_form(doctransform):
    assert(doctransform.doc["doc_type"] == "XFormInstance")
    form = XFormInstance.wrap(doctransform.doc)
    xml = doctransform.attachments.get("form.xml", "")
    if form.xmlns in FORM_CONFIG:
        rootxml = etree.XML(xml)
        for proppath, generatorfunc in FORM_CONFIG[form.xmlns].items():
            parts = proppath.split("/")
            node = form.form
            xmlnode = rootxml
            for i, p in enumerate(parts):
                if p in node:
                    xml_index = "{%(ns)s}%(val)s" % {"ns": form.xmlns, "val": p}
                    if i == len(parts) - 1:
                        # override prop on the last step
                        val = str(generatorfunc())
                        node[p] = val
                        xmlnode.find(xml_index).text = val
                    else:
                        # or drill in
                        node = node[p]
                        # NOTE: currently will not work with repeated nodes
                        xmlnode = xmlnode.find(xml_index)
                else:
                    # no index to the property, so assume we don't 
                    # need to touch it
                    break
        doctransform.doc = form._doc
        doctransform.attachments["form.xml"] = etree.tostring(rootxml)
        return doctransform
    else:
        # if we didn't know how to deidentify it, we don't want
        # to return anything, to prevent potentially identified
        # data from sneaking in
        return None
    