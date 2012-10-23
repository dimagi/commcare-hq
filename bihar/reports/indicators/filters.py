
# for now we do in-memory filtering, but should consider the implications
# before diving too far down that road.

def is_pregnant_mother(case):
    return case.type == "cc_bihar_pregnancy"

def became_pregnant_last_month(case):
    return is_pregnant_mother(case) and True
    