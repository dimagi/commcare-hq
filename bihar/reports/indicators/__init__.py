from collections import defaultdict
from dimagi.utils.modules import to_function

# static config - should this eventually live in the DB?
INDICATOR_SETS = [
    {
        "slug": "homevisit", 
        "name": "Home Visit Information",
        "indicators": {
            "summary": [
                {
                    "slug": "bp2",
                    "name": "BP (2nd Tri) Visits in last 30 days",
                    "calculation_function": "bihar.reports.indicators.calculations.bp2_last_month"
                },
                {"slug": "bp3", "name": "BP (3rd Tri) Visits in last 30 days"},
                {"slug": "pnc", "name": "PNC Visits  in last 30 days"},
                {"slug": "ebf", "name": "EBF Visits  in last 30 days"},
                {"slug": "cf", "name": "CF  Visits  in last 30 days"},
            ],
            "client_list": [
                {
                    "slug": "new_pregnancies", 
                    "name": "Pregnant woman registered in last 30 days",
                    "filter_function": "bihar.reports.indicators.filters.pregnancy_registered_last_month"
                }, 
                {
                    "slug": "deliveries", 
                    "name": "Pregnant woman who delivered in last 30 days",
                    "filter_function": "bihar.reports.indicators.filters.delivered_last_month"
                },
                {
                    "slug": "upcoming_deliveries", 
                    "name": "All woman due for delivery in next 30 days",
                    "filter_function": "bihar.reports.indicators.filters.due_next_month"
                }
            ]
        }
    },
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
        self.indicators = defaultdict(lambda: [])
        for type, list in spec.get("indicators", {}).items():
            self.indicators[type] = [Indicator(ispec) for ispec in list]  
                
    def get_indicators(self, type):
        return self.indicators[type]
    
    def get_indicator(self, type, slug):
        return _one(lambda i: i.slug == slug, self.indicators[type])
    
    
    
class Indicator(object):
    
    def __init__(self, spec):
        self.slug = spec["slug"]
        self.name = spec["name"]
        self.filter_function = to_function(spec["filter_function"]) \
            if "filter_function" in spec else None
        self.calculation_function = to_function(spec["calculation_function"]) \
            if "calculation_function" in spec else None
