from datetime import datetime, timedelta

# for now we do in-memory filtering, but should consider the implications
# before diving too far down that road.

A_MONTH = timedelta(days=30)
def is_pregnant_mother(case):
    return case.type == "cc_bihar_pregnancy"
 
def created_last_month(case):
    return case.opened_on > datetime.today() - A_MONTH
    
def pregnancy_registered_last_month(case):
    return is_pregnant_mother(case) and created_last_month(case)

def delivered_last_month(case):
    def _delivered_last_month(case):
        add = getattr(case, "add", None)
        return add and add > datetime.today().date() - A_MONTH
         
    return is_pregnant_mother(case) and _delivered_last_month(case)

def due_next_month(case):
    def _due_next_month(case):
        edd = getattr(case, "edd", None)
        add = getattr(case, "add", None)
        today = datetime.today().date()
        return edd and edd >= today and edd < today + A_MONTH and not add
         
    return is_pregnant_mother(case) and _due_next_month(case)

