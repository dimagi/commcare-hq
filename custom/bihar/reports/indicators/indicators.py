from __future__ import absolute_import
from inspect import ismethod
from dimagi.utils.decorators.memoized import memoized
from django.utils.html import format_html
from custom.bihar.calculations.types import DoneDueCalculator, TotalCalculator
from custom.bihar.models import CareBiharFluff
from custom.bihar.utils import get_all_owner_ids_from_group
from custom.bihar.reports.indicators.clientlistdisplay import PreDeliveryDoneDueCLD, PreDeliveryCLD, PreDeliverySummaryCLD, PostDeliverySummaryCLD, ComplicationsCalculator, PostDeliveryDoneDueCLD
from django.utils.translation import ugettext_noop as _
from six.moves import zip
from six.moves import map


# static config - should this eventually live in the DB?
DELIVERIES = {
    "slug": "deliveries",
    "name": _("Pregnant woman who delivered"),
    "clientlistdisplay": PreDeliveryCLD,
}
INDICATOR_SETS = [
    {
        "slug": "homevisit",
        "name": _("Home Visit Information"),
        "indicators": [
            {
                "slug": "bp2",
                "name": _("BP (2nd Tri) Visits"),
                "clientlistdisplay": PreDeliveryDoneDueCLD,
            },
            {
                "slug": "bp3",
                "name": _("BP (3rd Tri) Visits"),
                "clientlistdisplay": PreDeliveryDoneDueCLD,
            },
            {
                "slug": "pnc",
                "name": _("PNC Visits"),
                "clientlistdisplay": PostDeliveryDoneDueCLD,
            },
            {
                "slug": "ebf",
                "name": _("EBF Visits"),
                "clientlistdisplay": PostDeliveryDoneDueCLD,
            },
            {
                "slug": "cf",
                "name": _("CF Visits"),
                "clientlistdisplay": PostDeliveryDoneDueCLD,
            },
            {
                "slug": "upcoming_deliveries",
                "name": _("All woman due for delivery in next 30 days"),
                "clientlistdisplay": PreDeliveryCLD,
            },
            DELIVERIES,
            {
                "slug": "new_pregnancies",
                "name": _("Pregnant woman registered in last 30 days"),
                "clientlistdisplay": PreDeliveryCLD,
            },
            {
                "slug": "no_bp_counseling",
                "name": _("Pregnant woman not given BP counselling"),
                "clientlistdisplay": PreDeliveryCLD,
            },
            {
                "slug": "no_ifa_tablets",
                "name": _("Pregnant woman not received IFA tablets"),
                "clientlistdisplay": PreDeliveryCLD,
            },
            {
                "slug": "no_emergency_prep",
                "name": _("Woman due for delivery within 30 days who have not done preparation for Emergency Maternal Care"),
                "clientlistdisplay": PreDeliveryCLD,
            },
            {
                "slug": "no_newborn_prep",
                "name": _("Woman due for delivery within 30 days who have not done preparation for immediate new-born care"),
                "clientlistdisplay": PreDeliveryCLD,
            },
            {
                "slug": "no_postpartum_counseling",
                "name": _("Woman due for delivery within 30 days who have not been counselled on Immediate Post-Partum Family Planning"),
                "clientlistdisplay": PreDeliveryCLD,
            },
            {
                "slug": "no_family_planning",
                "name": _("Woman due for delivery within 30 days who have not showed interest to adopt Family planning methods"),
                "clientlistdisplay": PreDeliveryCLD,
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
                "clientlistdisplay": PostDeliverySummaryCLD,
            },
            {
                "slug": "idv",
                "name": _("Institutional Deliveries visited in 24 hours of Birth"),
                "clientlistdisplay": PostDeliverySummaryCLD,
            },
            {
                "slug": "idnb",
                "name": _("Institutional deliveries not breastfed within one hour"),
                "clientlistdisplay": PostDeliverySummaryCLD,
            },
            DELIVERIES,
            {
                "slug": "born_at_home",
                "name": _("Live Births at Home / Total Live Birth (TLB)"),
                "clientlistdisplay": PostDeliverySummaryCLD,
            },
            {
                "slug": "born_at_public_hospital",
                "name": _("Live Births at Government Hospital / Total Live Birth (TLB)"),
                "clientlistdisplay": PostDeliverySummaryCLD,
            },
            {
                "slug": "born_in_transit",
                "name": _("Live Births in Transit / Total Live Birth (TLB)"),
                "clientlistdisplay": PostDeliverySummaryCLD,
            },
            {
                "slug": "born_in_private_hospital",
                "name": _("Live Births at Private Hospital / Total Live Birth (TLB)"),
                "clientlistdisplay": PostDeliverySummaryCLD,
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
                "clientlistdisplay": ComplicationsCalculator,
                "kwargs": {'days': 1},
            },
            {
                "slug": 'comp3',
                "name": _("complications identified within 3 days of birth"),
                "clientlistdisplay": ComplicationsCalculator,
                "kwargs": {'days': 3},
            },
            {
                "slug": 'comp5',
                "name": _("complications identified within 5 days of birth"),
                "clientlistdisplay": ComplicationsCalculator,
                "kwargs": {'days': 5},
            },
            {
                "slug": 'comp7',
                "name": _("complications identified within 7 days of birth"),
                "clientlistdisplay": ComplicationsCalculator,
                "kwargs": {'days': 7},
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
                "clientlistdisplay": PreDeliverySummaryCLD,
            },
            {
                "slug": "lt2kglb",
                "name": _("infants < 2kg"),
                "clientlistdisplay": PreDeliverySummaryCLD,
            },
            {
                "slug": "visited_weak_ones",
                "name": _("visited Weak Newborn within 24 hours of birth by FLW"),
                "clientlistdisplay": PreDeliverySummaryCLD,
            },
            {
                "slug": "skin_to_skin",
                "name": _("weak newborn not receiving skin to skin care message by FLW"),
                "clientlistdisplay": PreDeliverySummaryCLD,
            },
            {
                "slug": "feed_vigour",
                "name": _("weak newborn not breastfeeding vigorously "),
                "clientlistdisplay": PreDeliverySummaryCLD,
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
                "clientlistdisplay": PreDeliverySummaryCLD,
            },
            {
                "slug": "adopted_fp",
                "name": _("# Adopted FP / # expressed interest in family planning & delivered in last 30 days"),
                "clientlistdisplay": PreDeliverySummaryCLD,
            },
            {
                "slug": "exp_int_fp",
                "name": _("# expressed interest in family planning / total # clients"),
                "clientlistdisplay": PreDeliverySummaryCLD,
            },
            {
                "slug": "no_fp",
                "name": _("clients who delivered in last 7 days and have not yet adopted FP"),
                "clientlistdisplay": PreDeliverySummaryCLD,
            },
            {
                "slug": "pregnant_fp",
                "name": _("# clients who whose EDD is in 30 days and have expressed interest in FP"),
                "clientlistdisplay": PreDeliverySummaryCLD,
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
                "clientlistdisplay": PostDeliverySummaryCLD,
            },
            {
                "slug": "infant_mortality",
                "name": _("Infants died"),
                "clientlistdisplay": PostDeliverySummaryCLD,
            },
            {
                "slug": "still_birth_public",
                "name": _("Still Births at Government Hospital"),
                "clientlistdisplay": PostDeliverySummaryCLD,
            },
            {
                "slug": "still_birth_home",
                "name": _("Still Births at Home"),
                "clientlistdisplay": PostDeliverySummaryCLD,
            },
            {
                "slug": "live_birth",
                "name": _("Live Births"),
                "clientlistdisplay": PostDeliverySummaryCLD,
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
        from django.utils.datastructures import SortedDict
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
        display = spec["clientlistdisplay"]
        kwargs = spec.get("kwargs", {})
        self._display = display(**kwargs)
        self.fluff_calculator = CareBiharFluff.get_calculator(self.slug)

    @property
    def show_in_client_list(self):
        return isinstance(self.fluff_calculator, TotalCalculator)

    @property
    def show_in_indicators(self):
        return isinstance(self.fluff_calculator, DoneDueCalculator)

    def get_columns(self):
        return self._display.get_columns()

    def sortkey(self, case, context):
        return self._display.sortkey(case, context)

    @property
    def sort_index(self):
        return self._display.sort_index

    def as_row(self, case, context, fluff_row):
        return self._display.as_row(case, context, fluff_row)


class IndicatorDataProvider(object):

    def __init__(self, domain, indicator_set, groups):
        self.domain = domain
        self.indicator_set = indicator_set
        self.groups = groups

    @property
    @memoized
    def all_owner_ids(self):
        return set([id for group in self.groups for id in get_all_owner_ids_from_group(group)])

    @property
    def summary_indicators(self):
        return [i for i in self.indicator_set.get_indicators() if i.show_in_indicators]

    @memoized
    def get_indicator_data(self, indicator):
        calculator = indicator.fluff_calculator
        assert calculator

        def pairs():
            for owner_id in self.all_owner_ids:
                result = calculator.get_result(
                    [self.domain, owner_id]
                )
                yield (result['numerator'], result['total'])
        # (0, 0) to set the dimensions
        # otherwise if results is ()
        # it'll be num, denom = () and that'll raise a ValueError
        num, denom = list(map(sum, zip((0, 0), *pairs())))
        return num, denom

    def get_indicator_value(self, indicator):
        return "%s/%s" % self.get_indicator_data(indicator)

    @memoized
    def get_case_ids(self, indicator):
        return self.get_case_data(indicator).keys()

    @memoized
    def get_case_data(self, indicator):
        results = indicator.fluff_calculator.aggregate_results(
            ([self.domain, owner_id] for owner_id in self.all_owner_ids),
            reduce=False
        )
        numerator = results['numerator']
        denominator = results[indicator.fluff_calculator.primary]
        return dict((id, {'num': id in numerator, 'denom': id in denominator}) for id in numerator | denominator)

    def get_chart(self, indicator):
        # this is a serious hack for now
        pie_class = 'sparkpie'
        num, denom = self.get_indicator_data(indicator)
        chart_template = (
            '<span data-numerator="{num}" '
            'data-denominator="{denom}" class="{pie_class}"></span>'
        )
        return format_html(chart_template, num=num,
                           denom=denom - num,
                           pie_class=pie_class)


def flatten_config():
    props = """
        slug
        name
        show_in_client_list
        show_in_indicators
        get_columns
    """.strip().split()
    config = IndicatorConfig(INDICATOR_SETS)
    r = []
    for indicator_set in config.indicator_sets:
        indicators = []
        r.append({
            'name': indicator_set.name,
            'slug': indicator_set.slug,
            'indicators': indicators,
        })
        for indicator in indicator_set.get_indicators():
            base, = indicator._calculator.__class__.__bases__
            indicator_d = {
                'caselistdisplay': base.__module__ + '.' + base.__name__
            }
            for p in props:
                val = getattr(indicator, p)
                if ismethod(val):
                    val = val()
                indicator_d[p] = val
            indicators.append(indicator_d)
    return r
