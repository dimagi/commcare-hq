#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4

from django.template.loader import render_to_string
from datetime import datetime, timedelta
from apps.reports.models import Case
import logging
'''Report file for custom Grameen reports'''
# see mvp.py for an explanation of how these are used.


def government(request):
    '''Government Report'''
    context = {}
    case_name = "Pathfinder CHBCP"
    try:
        case = Case.objects.get(name=case_name)
    except Case.DoesNotExist:
        return '''Sorry, it doesn't look like the forms that this report 
                  depends on have been uploaded.'''
    print "getting data"
    all_data = case.get_all_data_maps()
    print "got data"
    # the case ids come back as chwid|case
    # we want to bucketize them by chw first
    data_by_chw = {}
    print "organizing by chw"
    for id, map in all_data.items():
        chw_id = id.split("|")[0]
        if not chw_id in data_by_chw:
            data_by_chw[chw_id] = {}
        data_by_chw[chw_id][id] = map
    print "organized"
    chw_data_list = []
    enddate = datetime.now().date()
    startdate = enddate - timedelta(days=30)
    for chw_id, chw_data in data_by_chw.items():
        chw_obj = PathfinderCHWData(case, chw_id, chw_data, startdate, enddate)
        chw_data_list.append(chw_obj)
    context["all_data"] = chw_data_list[:10]
    return render_to_string("custom/pathfinder/government_report.html", context)

class PathfinderCHWData(object):
    '''Class to store all the data we need to access in a single
       row of the government report'''
    
    # initialize all the fields 
    case = None
    chw_id = None
    chw_name = None
    deaths = 0
    transfers = 0
    not_at_home = 0
    new_phla = 0
    new_chron = 0
    first_visit_plha = 0
    first_visit_chron = 0
    freq_vists_plha = 0
    freq_visits_chron = 0
    male = 0
    female = 0
    ref_vct = 0
    ref_oi = 0
    ref_ctc = 0
    ref_ctc_arv = 0
    ref_pmtct = 0
    ref_fp = 0
    ref_sg = 0
    ref_ovc = 0
    ref_tb = 0
    drug_counts = {}
    itns_waterguard_supplied = {}
    pcg_new_male = 0
    pcg_new_female = 0
    pcg_existing_male = 0
    pcg_existing_female = 0
    reg_forms = 0
    followup_forms = 0
    clients = 0
    
    def __init__(self, case, chw_id, data_map, startdate, enddate):
        self.case = case
        self.chw_id = chw_id
        self.startdate = startdate
        self.enddate = enddate
        
        for client_id, client_data in data_map.items():
            [reg_forms, followup_forms] =\
                [client_data[form] for form in case.form_identifiers]
            if reg_forms:
                for reg in reg_forms:
                    if not self.chw_name and reg["meta_username"]:
                        self.chw_name = reg["meta_username"]
                    elif self.chw_name and reg["meta_username"]:
                        if self.chw_name != reg["meta_username"]:
                            logging.debug("Warning, multiple ids found for %s: %s and %s" %\
                                (self.chw_id, self.chw_name, reg["meta_username"]))
                    
                self.reg_forms += len(reg_forms)
            self.followup_forms += len(followup_forms)
            self.clients += 1
