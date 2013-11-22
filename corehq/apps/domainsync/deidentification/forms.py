'''
Created on Nov 30, 2011

@author: czue
'''
from dimagi.utils.data.generator import random_phonenumber, arbitrary_fullname,\
    arbitrary_lastname, arbitrary_username
from lxml import etree
import random
from couchforms.models import XFormInstance

def random_momage():
    return random.randint(14, 55)

def random_yesno():
    return random.choice(("yes", "no"))

CRS_REGISTRATION = "http://openrosa.org/formdesigner/393CC825-7874-40E7-9AC6-927B09E832EC"
CRS_CHECKLIST = "http://openrosa.org/formdesigner/51283B9F-F810-44C9-8BCE-0A170F917BC1"
CRS_BIRTH = "http://openrosa.org/formdesigner/B3CEEEFF-0673-4AAF-8A77-AC6C0DB68ADD"

FORM_CONFIG = { CRS_REGISTRATION: {
                    "full_name": arbitrary_fullname,
                    "age": random_momage,
                    "number": random_phonenumber,
                    "husband_name": arbitrary_fullname,
                    "hamlet_name": arbitrary_lastname,
                    "case/create/case_name": arbitrary_fullname,
                    "case/update/husband_name": arbitrary_fullname,
                    "meta/username": arbitrary_username },
                CRS_CHECKLIST: {
                    "client_name": arbitrary_fullname,
                    "meta/username": arbitrary_username,
                    # all the yes/no's that we want to randomize
                    # this is pretty ugly but we'll deal with it for now
                    "previous_registration_done": random_yesno, 
                    "previous_tetanus_done": random_yesno, 
                    "previous_knows_closest_facility": random_yesno, 
                    "previous_transportation_contact": random_yesno, 
                    "previous_prepared_for_cost": random_yesno, 
                    "previous_institutional_delivery_plan": random_yesno, 
                    "previous_anc_1": random_yesno, 
                    "previous_anc_2": random_yesno, 
                    "previous_anc_3": random_yesno, 
                    "previous_anc_4": random_yesno, 
                    "previous_tetanus_previous": random_yesno, 
                    "previous_tetanus_booster": random_yesno, 
                    "previous_tetanus_1": random_yesno, 
                    "previous_tetanus_2": random_yesno, 
                    "previous_iron_folic_info": random_yesno, 
                    "previous_manual_labor_info": random_yesno, 
                    "registration_done": random_yesno, 
                    "anc_1": random_yesno, 
                    "anc_2": random_yesno, 
                    "anc_3": random_yesno, 
                    "anc_4": random_yesno, 
                    "tetanus_previous": random_yesno, 
                    "tetanus_booster": random_yesno, 
                    "tetanus_1": random_yesno, 
                    "tetanus_2": random_yesno, 
                    "takes_iron_folic": random_yesno, 
                    "more_iron_folic_practice": random_yesno, 
                    "manual_labor_info": random_yesno, 
                    "takes_nutrition": random_yesno, 
                    "danger_signs_quiz": random_yesno, 
                    "early_rupture_info": random_yesno, 
                    "early_labor_info": random_yesno, 
                    "severe_headache_info": random_yesno, 
                    "bleeding_unconscious_info": random_yesno, 
                    "no_placenta_info": random_yesno, 
                    "preparedness_info": random_yesno, 
                    "knows_closest_facility": random_yesno, 
                    "prepared_for_cost": random_yesno, 
                    "institutional_delivery_plan": random_yesno, 
                    "continuous_bleeding_info": random_yesno, 
                    "stops_kicking_info": random_yesno, 
                    "convulsions_info": random_yesno, 
                    "transportation_contact": random_yesno, 
                    "five_cleans_quiz": random_yesno, 
                    "newborn_warmth_info": random_yesno, 
                    "first_hour_breastfeeding_info": random_yesno, 
                    "first_milk_breastfeeding_info": random_yesno, 
                    "exclusive_breastfeeding_info": random_yesno, 
                    "newborn_danger_signs_info": random_yesno, 
                    "sons_daughters_same_info": random_yesno, 
                    "family_present": random_yesno,
                    "case/update/institutional-delivery-plan": random_yesno,
                    "case/update/transportation-contact": random_yesno,
                    "case/update/prepared-for-cost": random_yesno,
                    "case/update/takes-iron-folic": random_yesno,
                    "case/update/registration-done": random_yesno,
                    "case/update/anc-4": random_yesno,
                    "case/update/anc-2": random_yesno,
                    "case/update/anc-3": random_yesno,
                    "case/update/anc-1": random_yesno,
                    "case/update/tetanus-1": random_yesno,
                    "case/update/tetanus-2": random_yesno,
                    "case/update/manual-labor-info": random_yesno,
                    "case/update/knows-closest-facility": random_yesno },
                CRS_BIRTH: {
                    "meta/username": arbitrary_username }
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
