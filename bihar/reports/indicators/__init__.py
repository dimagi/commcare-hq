from collections import defaultdict
import functools
from django.conf import settings
from dimagi.utils.modules import to_function
from django.utils.translation import ugettext_noop as _
from dimagi.utils.parsing import string_to_datetime
from django.utils.datastructures import SortedDict

# change here to debug as if today were some day in the past
#now = string_to_datetime('2012-03-21')
now = None


DEFAULT_ROW_FUNCTION = 'bihar.reports.indicators.filters.mother_pre_delivery_columns'

# static config - should this eventually live in the DB?
DELIVERIES = {
    "slug": "deliveries",
    "name": _("Pregnant woman who delivered in last 30 days"),
    "filter_function": "bihar.reports.indicators.filters.delivered_last_month",
    "row_function": "bihar.reports.indicators.filters.mother_post_delivery_columns",
    "sortkey": "bihar.reports.indicators.filters.get_add_sortkey",
    "columns": [_("Name"), _("Husband's Name"), _("ADD")],
    }
INDICATOR_SETS = [
    {
        "slug": "homevisit", 
        "name": _("Home Visit Information"),
        "indicators": [
            {
                "slug": "bp2",
                "name": _("BP (2nd Tri) Visits in last 30 days (Done/Due)"),
                "calculation_class": "bihar.reports.indicators.calculations.BP2Calculator"
            },
            {
                "slug": "bp3",
                "name": _("BP (3rd Tri) Visits in last 30 days (Done/Due)"),
                "calculation_function": "bihar.reports.indicators.calculations.bp3_last_month"
            },
            {
                "slug": "pnc",
                "name": _("PNC Visits  in last 30 days (Done/Due)"),
                "calculation_function": "bihar.reports.indicators.calculations.pnc_last_month"
            },
            {
                "slug": "ebf",
                "name": _("EBF Visits in last 30 days (Done/Due)"),
                "calculation_function": "bihar.reports.indicators.calculations.eb_last_month"
            },
            {
                "slug": "cf",
                "name": _("CF Visits in last 30 days (Done/Due)"),
                "calculation_function": "bihar.reports.indicators.calculations.cf_last_month"
            },
            {
                "slug": "upcoming_deliveries", 
                "name": _("All woman due for delivery in next 30 days"),
                "filter_function": "bihar.reports.indicators.filters.due_next_month",
                "row_function": "bihar.reports.indicators.filters.mother_pre_delivery_columns",
                "sortkey": "bihar.reports.indicators.filters.get_edd_sortkey",
            },
            DELIVERIES,
            {
                "slug": "new_pregnancies", 
                "name": _("Pregnant woman registered in last 30 days"),
                "filter_function": "bihar.reports.indicators.filters.pregnancy_registered_last_month",
                "row_function": "bihar.reports.indicators.filters.mother_pre_delivery_columns",
                "sortkey": "bihar.reports.indicators.filters.get_edd_sortkey",
            },
            {
                "slug": "no_bp_counseling",
                "name": _("Pregnant woman not given BP counselling (of pregnant woman registered in last 30 days)"),
                "filter_function": "bihar.reports.indicators.filters.no_bp_counseling",
                "row_function": "bihar.reports.indicators.filters.mother_pre_delivery_columns",
                "sortkey": "bihar.reports.indicators.filters.get_edd_sortkey",
            },
            {
                "slug": "no_ifa_tablets",
                "name": _("Pregnant woman not received IFA tablets (of pregnant woman registered in last 30 days)"),
                "filter_function": "bihar.reports.indicators.filters.no_ifa_tablets",
                "row_function": "bihar.reports.indicators.filters.mother_pre_delivery_columns",
                "sortkey": "bihar.reports.indicators.filters.get_edd_sortkey",
            },
#                {
#                    "slug": "",
#                    "name": _("Women due for delivery within 30 days who have not done preparation for Emergency Maternal Care")
#                },
#                {
#                    "slug": "",
#                    "name": _("Women due for delivery within 30 days who have not done preparation for immediate new-born")
#                },
#                {
#                    "slug": "",
#                    "name": _("Women due for delivery within 30 days who have not been counselled on Immediate Post-Partum Family Planning")
#                },
#                {
#                    "slug": "",
#                    "name": _("Women due for delivery within 30 days who have not showed interest to adopt Family planning methods")
#                }
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
                "calculation_function": "bihar.reports.indicators.calculations.complications",
                "calculation_kwargs": {'days': 1, 'now': now},
            },
            {
                "slug": 'comp3',
                "name": _("# complications identified within 3 days of birth / # complications in last 30 days"),
                "calculation_function": "bihar.reports.indicators.calculations.complications",
                "calculation_kwargs": {'days': 3, 'now': now},
            },
            {
                "slug": 'comp5',
                "name": _("# complications identified within 5 days of birth / # complications in last 30 days"),
                "calculation_function": "bihar.reports.indicators.calculations.complications",
                "calculation_kwargs": {'days': 5, 'now': now},
            },
            {
                "slug": 'comp7',
                "name": _("# complications identified within 7 days of birth / # complications in last 30 days"),
                "calculation_function": "bihar.reports.indicators.calculations.complications",
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
            },
        ]
    },
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
        self.indicators = SortedDict()
        for ispec in spec.get("indicators", []):
            self.indicators[ispec["slug"]] = Indicator(ispec)
                
    def get_indicators(self, type):
        print "this is broken!"
        return self.indicators.values()
    
    def get_indicator(self, slug):
        return self.indicators[slug]

class Indicator(object):
    # this class is currently used both for client list filters and 
    # calculations.

    def __init__(self, spec):
        self.slug = spec["slug"]
        self.name = spec["name"]

        self.calculation_class = to_function(spec["calculation_class"])() \
            if "calculation_class" in spec else None

        self.calculation_function = to_function(spec["calculation_function"]) \
            if "calculation_function" in spec else None
        if spec.has_key("calculation_kwargs"):
            self.calculation_function = functools.partial(self.calculation_function, **spec['calculation_kwargs'])
        
        # case filter stuff
        self.filter_function = to_function(spec["filter_function"]) \
            if "filter_function" in spec else None
        self.sortkey = to_function(spec["sortkey"]) \
            if "sortkey" in spec else None
        self.row_function = to_function(spec.get("row_function", DEFAULT_ROW_FUNCTION))
        self.columns = spec.get("columns", [_("Name"), _("Husband's Name"), _("EDD")])

    def get_columns(self):
        if self.calculation_class:
            return self.calculation_class.get_columns()
        return self.columns