from bihar.reports.indicators.filters import A_MONTH
from datetime import datetime


EMPTY = (0,0)

def bp2_last_month(cases):
    # NOTE: cases in, values out might not be the right API
    # but it's what we need for the first set of stuff.
    # might want to revisit.
    
    # 1) 2nd Tri BP
    # filter by edd that meets: (edd - 196 <= today() < edd-98)
    # 2nd tri bp due = count date_bp_1 or date_bp_2 or date_bp_3 
    # 2nd tri bp done = count last_visit_type = 'bp' 
    
    # pseudo-code starting:
    #    for case in cases:
    #        for a in case.actions:
    #            if a.date > datetime.today() + A_MONTH:
    #                return True
        
    return "bp2 filler"