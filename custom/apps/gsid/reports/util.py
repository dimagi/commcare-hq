from corehq.apps.fixtures.models import FixtureDataItem, FixtureDataType
from corehq.apps.reports.util import make_form_couch_key
from couchforms.models import XFormInstance
import logging


def get_unique_combinations(domain, place_types=None, place=None):
    if not place_types:
        return []
    if place:
        place_type = place[0]
        place = FixtureDataItem.get(place[1])
        place_name = place.fields_without_attributes[place_type + '_id']

    place_data_types = {}
    for pt in place_types:
        place_data_types[pt] = FixtureDataType.by_domain_tag(domain, pt).one()

    relevant_types = [t for t in reversed(place_types)]
    base_type = relevant_types[0] if relevant_types else ""
    fdis = FixtureDataItem.by_data_type(domain, place_data_types[base_type].get_id) if base_type else []

    combos = []
    for fdi in fdis:
        if place:
            if base_type == place_type:
                if fdi.fields_without_attributes[base_type + '_id'] != place_name:
                    continue
            else:
                rel_type_name = fdi.fields_without_attributes.get(place_type+"_id", "")
                if not rel_type_name:
                    logging.error("GSID Reports Error: fixture_id: %s -- place_type: %s" % (fdi.get_id, place_type))
                    continue
                if rel_type_name.lower() != place_name:
                    continue
        comb = {}
        for pt in place_types:
            if base_type == pt:
                comb[pt] = str(fdi.fields_without_attributes[pt + '_id'])
                comb["gps"] = str(fdi.fields_without_attributes["gps"])
            else:
                p_id = fdi.fields_without_attributes.get(pt + "_id", None)
                if p_id:
                    if place and pt == place_type and p_id != place_name:
                        continue
                    comb[pt] = str(p_id)
                else:
                    comb[pt] = None
        combos.append(comb)
    return combos


def capitalize_fn(x):
    """
        Takes "high_point", returns "High Point".
        Bad implementation, should have been taken care in keys() method and 
        above get_unique_combinations() method. Needs too many changes to have
        same effect now.        
    """
    return x.replace("_", " ").title()
