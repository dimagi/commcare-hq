from datetime import datetime, timedelta
from bihar.reports.indicators.reports import DEFAULT_EMPTY

# for now we do in-memory filtering, but should consider the implications
# before diving too far down that road.
# hopefully these can one day be replaced by elastic search or equivalent.

A_MONTH = timedelta(days=30)

def is_pregnant_mother(case):
    return case.type == "cc_bihar_pregnancy"
 
def created_last_month(case):
    return case.opened_on > datetime.today() - A_MONTH
    
def delivered(case):
    return bool(getattr(case, "add", False))
        
def in_second_trimester(edd, reference_date=None):
    reference_date = reference_date or datetime.today().date()
    return edd <= first_tri_cutoff(reference_date) \
        and edd > second_tri_cutoff(reference_date) 

def in_third_trimester(edd, reference_date=None):
    reference_date = reference_date or datetime.today().date()
    return edd <= second_tri_cutoff(reference_date) \
        and edd > third_tri_cutoff(reference_date) 

def first_tri_cutoff(reference_date):
    # women with edd after this date are in their first trimester
    return reference_date + timedelta(days=196)

def second_tri_cutoff(reference_date):
    # women with edd after this date (but before first_tri_cutoff) 
    # are in their second trimester
    return reference_date + timedelta(days=98)

def third_tri_cutoff(reference_date):
    # women with edd after this date (but before second_tri_cutoff) 
    # are in their third trimester
    return reference_date + timedelta(days=-28)

def pregnancy_registered_last_month(case):
    return is_pregnant_mother(case) and created_last_month(case)

def delivered_last_month(case):
    def _delivered_last_month(case):
        add = get_add(case)
        return add and add > datetime.today().date() - A_MONTH
         
    return is_pregnant_mother(case) and _delivered_last_month(case)

def due_next_month(case):
    def _due_next_month(case):
        edd = get_edd(case)
        today = datetime.today().date()
        return edd and edd >= today - A_MONTH and edd < today + A_MONTH and not delivered(case)
         
    return is_pregnant_mother(case) and _due_next_month(case)

def mother_pre_delivery_columns(case):
    return (case.name, getattr(case, "edd", DEFAULT_EMPTY))

def mother_post_delivery_columns(case):
    return (case.name, getattr(case, "add", DEFAULT_EMPTY))

def get_edd(case):
    return getattr(case, 'edd', None)

def get_add(case):
    return getattr(case, 'add', None)
