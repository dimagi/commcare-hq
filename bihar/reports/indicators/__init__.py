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
    "name": _("Pregnant woman who delivered"),
    "calculation_class": "bihar.reports.indicators.home_visit.RecentDeliveryList",
}
INDICATOR_SETS = [
    {
        "slug": "homevisit", 
        "name": _("Home Visit Information"),
        "indicators": [
            {
                "slug": "bp2",
                "name": _("BP (2nd Tri) Visits"),
                "calculation_class": "bihar.reports.indicators.home_visit.BP2Calculator"
            },
            {
                "slug": "bp3",
                "name": _("BP (3rd Tri) Visits"),
                "calculation_class": "bihar.reports.indicators.home_visit.BP3Calculator"
            },
            {
                "slug": "pnc",
                "name": _("PNC Visits"),
                "calculation_class": "bihar.reports.indicators.home_visit.PNCCalculator"
            },
            {
                "slug": "ebf",
                "name": _("EBF Visits"),
                "calculation_class": "bihar.reports.indicators.home_visit.EBCalculator"
            },
            {
                "slug": "cf",
                "name": _("CF Visits"),
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
                "name": _("Pregnant woman not given BP counselling"),
                "calculation_class": "bihar.reports.indicators.home_visit.NoBPList",
            },
            {
                "slug": "no_ifa_tablets",
                "name": _("Pregnant woman not received IFA tablets"),
                "calculation_class": "bihar.reports.indicators.home_visit.NoIFAList",
            },
            {
                "slug": "no_emergency_prep",
                "name": _("Woman due for delivery within 30 days who have not done preparation for Emergency Maternal Care"),
                "calculation_class": "bihar.reports.indicators.home_visit.NoEmergencyPrep",
            },
            {
                "slug": "no_newborn_prep",
                "name": _("Woman due for delivery within 30 days who have not done preparation for immediate new-born care"),
                "calculation_class": "bihar.reports.indicators.home_visit.NoNewbornPrep",
            },
            {
                "slug": "no_postpartum_counseling",
                "name": _("Woman due for delivery within 30 days who have not been counselled on Immediate Post-Partum Family Planning"),
                "calculation_class": "bihar.reports.indicators.home_visit.NoPostpartumCounseling",
            },
            {
                "slug": "no_family_planning",
                "name": _("Woman due for delivery within 30 days who have not showed interest to adopt Family planning methods"),
                "calculation_class": "bihar.reports.indicators.home_visit.NoFamilyPlanning",
            },
        ]
    },
    {
        "slug": "pregnancy",
        "name": _("Pregnancy Outcomes"),
        "indicators": [
            {
                "slug": "hd",
                "name": _("Home Deliveries visited in 24 hours of Birth"),
                "calculation_class": "bihar.reports.indicators.calculations.HDDayCalculator"
            },
            {
                "slug": "idv",
                "name": _("Institutional Deliveries visited in 24 hours of Birth"),
                "calculation_class": "bihar.reports.indicators.calculations.IDDayCalculator"
            },
            {
                "slug": "idnb",
                "name": _("Institutional deliveries not breastfed within one hour"),
                "calculation_class": "bihar.reports.indicators.calculations.IDNBCalculator"
            },
            DELIVERIES,
            {
                "slug": "born_at_home",
                "name": _("Live Births at Home / Total Live Birth (TLB)"),
                "calculation_class": "bihar.reports.indicators.pregnancy_outcome.BornAtHomeCalculator",
            },
            {
                "slug": "born_at_public_hospital",
                "name": _("Live Births at Government Hospital / Total Live Birth (TLB)"),
                "calculation_class": "bihar.reports.indicators.pregnancy_outcome.BornAtPublicHospital",
            },
            {
                "slug": "born_in_transit",
                "name": _("Live Births in Transit / Total Live Birth (TLB)"),
                "calculation_class": "bihar.reports.indicators.pregnancy_outcome.BornInTransit",
            },
            {
                "slug": "born_in_private_hospital",
                "name": _("Live Births at Private Hospital / Total Live Birth (TLB)"),
                "calculation_class": "bihar.reports.indicators.pregnancy_outcome.BornInPrivateHospital",
            },
        ],
    },
    {
        "slug": "postpartum",
        "name": _("Post-Partum Complications"),
        "indicators": [
            {
                "slug": 'comp1',
                "name": _("complications identified in first 24 hours"),
                "calculation_class": "bihar.reports.indicators.calculations.ComplicationsCalculator",
                "calculation_kwargs": {'days': 1, 'now': now},
            },
            {
                "slug": 'comp3',
                "name": _("complications identified within 3 days of birth"),
                "calculation_class": "bihar.reports.indicators.calculations.ComplicationsCalculator",
                "calculation_kwargs": {'days': 3, 'now': now},
            },
            {
                "slug": 'comp5',
                "name": _("complications identified within 5 days of birth"),
                "calculation_class": "bihar.reports.indicators.calculations.ComplicationsCalculator",
                "calculation_kwargs": {'days': 5, 'now': now},
            },
            {
                "slug": 'comp7',
                "name": _("complications identified within 7 days of birth"),
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
                "name": _("Preterm births"),
                "calculation_class": "bihar.reports.indicators.calculations.PTLBCalculator"
            },
            {
                "slug": "lt2kglb",
                "name": _("infants < 2kg"),
                "calculation_class": "bihar.reports.indicators.calculations.LT2KGLBCalculator"
            },
            {
                "slug": "visited_weak_ones",
                "name": _("visited Weak Newborn within 24 hours of birth by FLW"),
                "calculation_class": "bihar.reports.indicators.calculations.VWOCalculator"
            },
            {
                "slug": "skin_to_skin",
                "name": _("weak newborn not receiving skin to skin care message by FLW"),
                "calculation_class": "bihar.reports.indicators.calculations.S2SCalculator"
            },
            {
                "slug": "feed_vigour",
                "name": _("weak newborn not breastfeeding vigorously "),
                "calculation_class": "bihar.reports.indicators.calculations.FVCalculator"
            },
        ]
    },
    {
        "slug": "familyplanning",
        "name": _("Family Planning"),
        "indicators": [
            {
                "slug": "interested_in_fp",
                "name": _("# Expressed interest in family planning / # deliveries in last 30 days"),
                "calculation_class": "bihar.reports.indicators.calculations.FPCalculator"
            },
            {
                "slug": "adopted_fp",
                "name": _("# Adopted FP / # expressed interest in family planning & delivered in last 30 days"),
                "calculation_class": "bihar.reports.indicators.calculations.AFPCalculator"
            },
            {
                "slug": "exp_int_fp",
                "name": _("# expressed interest in family planning / total # clients"),
                "calculation_class": "bihar.reports.indicators.calculations.EFPCalculator"
            },
            {
                "slug": "no_fp",
                "name": _("clients who delivered in last 7 days and have not yet adopted FP"),
                "calculation_class": "bihar.reports.indicators.calculations.NOFPCalculator"
            },
            {
                "slug": "pregnant_fp",
                "name": _("# clients who whose EDD is in 30 days and have expressed interest in FP"),
                "calculation_class": "bihar.reports.indicators.calculations.PFPCalculator"
            }
        ]
    },
#    {"slug": "complimentaryfeeding", "name": _("Complimentary Feeding") },
    {
        "slug": "mortality",
        "name": _("Mortality"),
        "indicators": [
            {
                "slug": "mother_mortality",
                "name": _("Mothers died"),
                "calculation_class": "bihar.reports.indicators.calculations.MMCalculator"
            },
            {
                "slug": "infant_mortality",
                "name": _("Infants died"),
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
        calculation_class = to_function(spec["calculation_class"], failhard=True)
        kwargs = spec.get("calculation_kwargs", {})
        self._calculator = calculation_class(**kwargs)

    @property
    def show_in_client_list(self):
        return self._calculator.show_in_client_list
    
    @property
    def show_in_indicators(self):
        return self._calculator.show_in_indicators
        
    def get_columns(self):
        return self._calculator.get_columns()

    @property
    def sortkey(self):
        return self._calculator.sortkey

    def filter(self, case):
        return self._calculator.filter(case)

    def as_row(self, case):
        return self._calculator.as_row(case)

    def display(self, cases):
        return self._calculator.display(cases)