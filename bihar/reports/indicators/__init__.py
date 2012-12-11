from collections import defaultdict
import functools
from django.conf import settings
from dimagi.utils.modules import to_function
from django.utils.translation import ugettext_noop as _
from dimagi.utils.parsing import string_to_datetime
from django.utils.datastructures import SortedDict

# change here to debug as if today were some day in the past
now = string_to_datetime('2012-03-21')
#now = None


DEFAULT_ROW_FUNCTION = 'bihar.reports.indicators.filters.mother_pre_delivery_columns'

# static config - should this eventually live in the DB?
DELIVERIES = {
    "slug": "deliveries",
    "name": _("Pregnant woman who delivered in last 30 days"),
    "calculation_class": "bihar.reports.indicators.home_visit.RecentDeliveryList",
}
INDICATOR_SETS = [
    {
        "slug": "homevisit", 
        "name": _("Home Visit Information"),
        "indicators": [
            {
                "slug": "bp2",
                "name": _("BP (2nd Tri) Visits in last 30 days (Done/Due)"),
                "calculation_class": "bihar.reports.indicators.home_visit.BP2Calculator"
            },
            {
                "slug": "bp3",
                "name": _("BP (3rd Tri) Visits in last 30 days (Done/Due)"),
                "calculation_class": "bihar.reports.indicators.home_visit.BP3Calculator"
            },
            {
                "slug": "pnc",
                "name": _("PNC Visits  in last 30 days (Done/Due)"),
                "calculation_class": "bihar.reports.indicators.home_visit.PNCCalculator"
            },
            {
                "slug": "ebf",
                "name": _("EBF Visits in last 30 days (Done/Due)"),
                "calculation_class": "bihar.reports.indicators.home_visit.EBCalculator"
            },
            {
                "slug": "cf",
                "name": _("CF Visits in last 30 days (Done/Due)"),
                "calculation_class": "bihar.reports.indicators.home_visit.CFCalculator"
            },
            {
                "slug": "upcoming_deliveries", 
                "name": _("All woman due for delivery in next 30 days"),
                "calculation_class": "bihar.reports.indicators.home_visit.UpcomingDeliveryList",
            },
            DELIVERIES,
            {
                "slug": "new_pregnancies", 
                "name": _("Pregnant woman registered in last 30 days"),
                "calculation_class": "bihar.reports.indicators.home_visit.RecentRegistrationList",
            },
            {
                "slug": "no_bp_counseling",
                "name": _("Pregnant woman not given BP counselling (of pregnant woman registered in last 30 days)"),
                "calculation_class": "bihar.reports.indicators.home_visit.NoBPList",
            },
            {
                "slug": "no_ifa_tablets",
                "name": _("Pregnant woman not received IFA tablets (of pregnant woman registered in last 30 days)"),
                "calculation_class": "bihar.reports.indicators.home_visit.NoBPList",    
            },
        ]
    },
    {
        "slug": "pregnancy",
        "name": _("Pregnancy Outcomes"),
        "indicators": [
            {
                "slug": "hd",
                "name": _("Home Deliveries visited in 24 hours of Birth (Total Number HD24HR/TNHD)"),
                "calculation_class": "bihar.reports.indicators.calculations.HDDayCalculator"
            },
            {
                "slug": "idv",
                "name": _("Institutional Deliveries visited in 24 hours of Birth (Total Number ID24HR/TNI)"),
                "calculation_class": "bihar.reports.indicators.calculations.IDDayCalculator"
            },
            {
                "slug": "idnb",
                "name": _("Institutional deliveries not breastfed within one hour (Total NumberBF/Total Number ID24HR)"),
                "calculation_class": "bihar.reports.indicators.calculations.IDNBCalculator"
            },
            DELIVERIES,
        ],
    },
    {
        "slug": "postpartum",
        "name": _("Post-Partum Complications"),
        "indicators": [
            {
                "slug": 'comp1',
                "name": _("# complications identified in first 24 hours / # complications in last 30 days"),
                "calculation_class": "bihar.reports.indicators.calculations.ComplicationsCalculator",
                "calculation_kwargs": {'days': 1, 'now': now},
            },
            {
                "slug": 'comp3',
                "name": _("# complications identified within 3 days of birth / # complications in last 30 days"),
                "calculation_class": "bihar.reports.indicators.calculations.ComplicationsCalculator",
                "calculation_kwargs": {'days': 3, 'now': now},
            },
            {
                "slug": 'comp5',
                "name": _("# complications identified within 5 days of birth / # complications in last 30 days"),
                "calculation_class": "bihar.reports.indicators.calculations.ComplicationsCalculator",
                "calculation_kwargs": {'days': 5, 'now': now},
            },
            {
                "slug": 'comp7',
                "name": _("# complications identified within 7 days of birth / # complications in last 30 days"),
                "calculation_class": "bihar.reports.indicators.calculations.ComplicationsCalculator",
                "calculation_kwargs": {'days': 7, 'now': now},
            },
        ],
    },
    {
        "slug": "newborn",
        "name": _("Weak Newborn"),
        "indicators": [
            {
                "slug": "ptlb",
                "name": _("# Preterm births / # Live births"),
                "calculation_class": "bihar.reports.indicators.calculations.PTLBCalculator"
            },
            {
                "slug": "lt2kglb",
                "name": _("# infants < 2kg / # live births"),
                "calculation_class": "bihar.reports.indicators.calculations.LT2KGLBCalculator"
            },
            {
                "slug": "visited_weak_ones",
                "name": _("# live births who are preterm or < 2kg  visited in 24 hours of birth by FLW/ (# preterm + # infants < 2kg)"),
                "calculation_class": "bihar.reports.indicators.calculations.VWOCalculator"
            },
            {
                "slug": "skin_to_skin",
                "name": _("# live births who are preterm and < 2kg not receiving skin to skin care message by FLW"),
                "calculation_class": "bihar.reports.indicators.calculations.S2SCalculator"
            },
            {
                "slug": "feed_vigour",
                "name": _("# live births who are preterm and < 2kg infants not breastfeeding vigorously "),
                "calculation_class": "bihar.reports.indicators.calculations.FVCalculator"
            },
        ]
    },
#    {"slug": "familyplanning", "name": _("Family Planning") },
#    {"slug": "complimentaryfeeding", "name": _("Complimentary Feeding") },
    {
        "slug": "mortality",
        "name": _("Mortality"),
        "indicators": [
            {
                "slug": "mother_mortality",
                "name": _("# Mothers who've died in the last 30 days"),
                "calculation_class": "bihar.reports.indicators.calculations.MMCalculator"
            },
            {
                "slug": "infant_mortality",
                "name": _("# Infants who've died in the last 30 days"),
                "calculation_class": "bihar.reports.indicators.calculations.IMCalculator"
            },
        ]
    }
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
        self.indicators = SortedDict()
        for ispec in spec.get("indicators", []):
            self.indicators[ispec["slug"]] = Indicator(ispec)
                
    def get_indicators(self):
        return self.indicators.values()
    
    def get_indicator(self, slug):
        return self.indicators[slug]

class Indicator(object):
    # this class is currently used both for client list filters and 
    # calculations.

    def __init__(self, spec):
        self.slug = spec["slug"]
        self.name = spec["name"]
        if "calculation_class" in spec:
            calculation_class = to_function(spec["calculation_class"])
            kwargs = spec.get("calculation_kwargs", {})
            self.calculation_class = calculation_class(**kwargs)
        else:
            self.calculation_class = None
        
        # case filter stuff
        self.filter_function = to_function(spec["filter_function"]) \
            if "filter_function" in spec else None
        self.sortkey = to_function(spec["sortkey"]) \
            if "sortkey" in spec else None
        self.row_function = to_function(spec.get("row_function", DEFAULT_ROW_FUNCTION))
        self.columns = spec.get("columns", [_("Name"), _("Husband's Name"), _("EDD")])

    @property
    def show_in_client_list(self):
        return self.calculation_class.show_in_client_list if \
            self.calculation_class else True
    
    @property
    def show_in_indicators(self):
        return self.calculation_class.show_in_indicators if \
            self.calculation_class else True
        
    def get_columns(self):
        if self.calculation_class:
            return self.calculation_class.get_columns()
        return self.columns