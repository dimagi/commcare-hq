from datetime import datetime, timedelta

# for now we do in-memory filtering, but should consider the implications
# before diving too far down that road.

def is_pregnant_mother(case):
    return case.type == "cc_bihar_pregnancy"
 
def created_last_month(case):
    return case.opened_on > datetime.today() - timedelta(days=30)
    
def pregnancy_registered_last_month(case):
    return is_pregnant_mother(case) and created_last_month(case)
    