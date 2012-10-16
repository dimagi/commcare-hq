

# static config - should this eventually live in the DB?
INDICATOR_SETS = [
    {"slug": "homevisit", "name": "Home Visit Information",
     "indicators": [
        {"slug": "bp2", "name": "BP (2nd Tri) Visits in last 30 days"},
        {"slug": "bp3", "name": "BP (3rd Tri) Visits in last 30 days"},
        {"slug": "pnc", "name": "PNC Visits  in last 30 days"},
        {"slug": "ebf", "name": "EBF Visits  in last 30 days"},
        {"slug": "cf", "name": "CF  Visits  in last 30 days"},
    ]},
    {"slug": "pregnancy", "name": "Pregnancy Outcome" },
    {"slug": "postpartum", "name": "Post-Partum Complications" },
    {"slug": "newborn", "name": "Weak Newborn" },
    {"slug": "familyplanning", "name": "Family Planning" },
    {"slug": "complimentaryfeeding", "name": "Complimentary Feeding" },
    {"slug": "mortality", "name": "Mortality" }
]

def _one(filter_func, list):
    # this will (intentionally) fail hard if not exactly 1 match
    [ret] = filter(filter_func, list)
    return ret

class IndicatorConfig(object):
    def __init__(self, spec):
        self.indicator_sets = [IndicatorSet(setspec) for setspec in spec]

    def get_indicator_set(self, slug):
        return _one(lambda i: i.slug == slug, self.indicator_sets)

class IndicatorSet(object):
    
    def __init__(self, spec):
        self.slug = spec["slug"]
        self.name = spec["name"]
        self.indicators = [Indicator(ispec) for ispec in (spec.get("indicators") or [])]
        
    def get_indicator(self, slug):
        return _one(lambda i: i.slug == slug, self.indicators)
    
class Indicator(object):
    
    def __init__(self, spec):
        self.slug = spec["slug"]
        self.name = spec["name"]
