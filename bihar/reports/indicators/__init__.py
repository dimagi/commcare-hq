from collections import defaultdict
from dimagi.utils.modules import to_function
from django.utils.translation import ugettext_noop as _

# static config - should this eventually live in the DB?
INDICATOR_SETS = [
    {
        "slug": "homevisit", 
        "name": _("Home Visit Information"),
        "indicators": {
            "summary": [
                {
                    "slug": "bp2",
                    "name": _("BP (2nd Tri) Visits in last 30 days"),
                    "calculation_function": "bihar.reports.indicators.calculations.bp2_last_month"
                },
                {
                    "slug": "bp3",
                    "name": _("BP (3rd Tri) Visits in last 30 days"),
                    "calculation_function": "bihar.reports.indicators.calculations.bp3_last_month"
                },
                {
                    "slug": "pnc",
                    "name": _("PNC Visits  in last 30 days"),
                    "calculation_function": "bihar.reports.indicators.calculations.pnc_last_month"
                },
                {
                    "slug": "ebf",
                    "name": _("EBF Visits in last 30 days"),
                    "calculation_function": "bihar.reports.indicators.calculations.eb_last_month"
                },
                {
                    "slug": "cf",
                    "name": _("CF Visits in last 30 days"),
                    "calculation_function": "bihar.reports.indicators.calculations.cf_last_month"
                },
            ],
            "client_list": [
                {
                    "slug": "upcoming_deliveries", 
                    "name": _("All woman due for delivery in next 30 days"),
                    "filter_function": "bihar.reports.indicators.filters.due_next_month",
                    "row_function": "bihar.reports.indicators.filters.mother_pre_delivery_columns",
                    "sortkey": "bihar.reports.indicators.filters.get_edd_sortkey",
                },
                {
                    "slug": "deliveries", 
                    "name": _("Pregnant woman who delivered in last 30 days"),
                    "filter_function": "bihar.reports.indicators.filters.delivered_last_month",
                    "row_function": "bihar.reports.indicators.filters.mother_post_delivery_columns",
                    "sortkey": "bihar.reports.indicators.filters.get_add_sortkey",
                    "columns": [_("Name"), _("ADD")],
                },
                {
                    "slug": "new_pregnancies", 
                    "name": _("Pregnant woman registered in last 30 days"),
                    "filter_function": "bihar.reports.indicators.filters.pregnancy_registered_last_month",
                    "row_function": "bihar.reports.indicators.filters.mother_pre_delivery_columns",
                    "sortkey": "bihar.reports.indicators.filters.get_edd_sortkey",
                }, 
            ]
        }
    },
#    {"slug": "pregnancy", "name": _("Pregnancy Outcome") },
#    {"slug": "postpartum", "name": _("Post-Partum Complications") },
#    {"slug": "newborn", "name": _("Weak Newborn") },
#    {"slug": "familyplanning", "name": _("Family Planning") },
#    {"slug": "complimentaryfeeding", "name": _("Complimentary Feeding") },
#    {"slug": "mortality", "name": _("Mortality") }
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
    # this class is currently used both for client list filters and 
    # calcualtions. it probably makes sense to pull them out into separate
    # things
    
    def __init__(self, spec):
        self.slug = spec["slug"]
        self.name = spec["name"]
        self.calculation_function = to_function(spec["calculation_function"]) \
            if "calculation_function" in spec else None
        
        # case filter stuff
        self.filter_function = to_function(spec["filter_function"]) \
            if "filter_function" in spec else None
        self.sortkey = to_function(spec["sortkey"]) \
            if "sortkey" in spec else None
        self.row_function = to_function(spec["row_function"]) \
            if "row_function" in spec else None
        self.columns = spec.get("columns", [_("Name"), _("EDD")])
        
    