from django.utils.translation import ugettext as _

from dimagi.utils.decorators.memoized import memoized

from .utils import normal_format, format_percent


class HealthStatus(object):

    # maps method name to header
    method_map = [
        ('awc', "AWC"),
        ('beneficiaries', "Total # of Beneficiaries Registered"),
        ('lmp', "# of Pregnant Women Registered"),
        ('mother_reg', "# of Mothers of Children Aged 3 Years and Below Registered"),
        ('childrens', "# of Children Between 0 and 3 Years of Age Registered"),
        ('vhnd_monthly', "# of Beneficiaries Attending VHND Monthly"),
        ('ifa_tablets', "# of Pregnant Women Who Have Received at least 30 IFA Tablets"),
        ('weight_once', "# of Pregnant Women Whose Weight Gain Was Monitored At Least Once"),
        ('weight_twice', "# of Pregnant Women Whose Weight Gain Was Monitored Twice"),
        ('children_monitored_at_birth', "# of Children Whose Weight Was Monitored at Birth"),
        ('children_registered', "# of Children Whose Birth Was Registered"),
        ('growth_monitoring_session_1', "# of Children Who Have Attended At Least 1 Growth Monitoring Session"),
        ('growth_monitoring_session_2', "# of Children Who Have Attended At Least 2 Growth Monitoring Sessions"),
        ('growth_monitoring_session_3', "# of Children Who Have Attended At Least 3 Growth Monitoring Sessions"),
        ('growth_monitoring_session_4', "# of Children Who Have Attended At Least 4 Growth Monitoring Sessions"),
        ('growth_monitoring_session_5', '# of Children Who Have Attended At Least 5 Growth Monitoring Sessions'),
        ('growth_monitoring_session_6', '# of Children Who Have Attended At Least 6 Growth Monitoring Sessions'),
        ('growth_monitoring_session_7', '# of Children Who Have Attended At Least 7 Growth Monitoring Sessions'),
        ('growth_monitoring_session_8', '# of Children Who Have Attended At Least 8 Growth Monitoring Sessions'),
        ('growth_monitoring_session_9', '# of Children Who Have Attended At Least 9 Growth Monitoring Sessions'),
        ('growth_monitoring_session_10', '# of Children Who Have Attended At Least 10 Growth Monitoring Sessions'),
        ('growth_monitoring_session_11', '# of Children Who Have Attended At Least 11 Growth Monitoring Sessions'),
        ('growth_monitoring_session_12', '# of Children Who Have Attended At Least 12 Growth Monitoring Sessions'),
        ('nutritional_status_normal', '# of Children Whose Nutritional Status is Normal'),
        ('nutritional_status_mam', '# of Children Whose Nutritional Status is "MAM"'),
        ('nutritional_status_sam', '# of Children Whose Nutritional Status is "SAM"'),
        ('ors_zinc', '# of Children Who Have Received ORS and Zinc Treatment if He/She Contracts Diarrhea'),
        ('breastfed', '# of Mothers of Children Aged 3 Years and Below Who Reported to Have Exclusively Breastfed Their Children for First 6 Months'),
        ('measlesvacc', '# of Children Who Received Measles Vaccine'),
    ]

    awc = None
    beneficiaries = normal_format(0)
    lmp = format_percent(1, 0)
    mother_reg = format_percent(1, 0)
    childrens = normal_format(0)
    vhnd_monthly = format_percent(1, 0)
    ifa_tablets = format_percent(1, 0)
    weight_once = format_percent(1, 0)
    weight_twice = format_percent(1, 0)
    children_monitored_at_birth = format_percent(1, 0)
    children_registered = format_percent(1, 0)
    growth_monitoring_session_1 = format_percent(1, 0)
    growth_monitoring_session_2 = format_percent(1, 0)
    growth_monitoring_session_3 = format_percent(1, 0)
    growth_monitoring_session_4 = format_percent(1, 0)
    growth_monitoring_session_5 = format_percent(1, 0)
    growth_monitoring_session_6 = format_percent(1, 0)
    growth_monitoring_session_7 = format_percent(1, 0)
    growth_monitoring_session_8 = format_percent(1, 0)
    growth_monitoring_session_9 = format_percent(1, 0)
    growth_monitoring_session_10 = format_percent(1, 0)
    growth_monitoring_session_11 = format_percent(1, 0)
    growth_monitoring_session_12 = format_percent(1, 0)
    nutritional_status_normal = format_percent(1, 0)
    nutritional_status_mam = format_percent(1, 0)
    nutritional_status_sam = format_percent(1, 0)
    ors_zinc = format_percent(1, 0)
    breastfed = format_percent(1, 0)
    measlesvacc = format_percent(1, 0)

    def __init__(self, **entries):
        self.__dict__.update(entries)


class AWCHealthStatus(object):
    """
    Takes a set of OPMCaseRow objects, all from the same AWC, and performs
    aggregations on it.
    """
    method_map = [
        # method, header, help_text, count_method
        ('awc_name',
         _("AWC Name"),
         "",
         'no_denom'),
        ('beneficiaries',
         _("Total Beneficiaries"),
         _("Pregnant women and children"),
         'no_denom'),
        ('pregnancies',
         _("Pregnant Women"),
         "",
         'beneficiaries'),
        ('mothers',
         _("New Mothers"),
         _("Mothers of children aged 3 years and below"),
         'beneficiaries'),
        ('children',
         _("Children"),
         _("Children below 3 years of age"),
         'beneficiaries'),
        ('eligible_by_fulfillment',
         _("Eligible By Fulfillment"),
        _("Number of beneficiaries eligilble for monthly cash payment in the "
          "presence of a VHND in the last month."),
         'beneficiaries'),
        ('eligible_by_default',
         _("Eligible By Default"),
        _("Number of beneficiaries eligilble for monthly cash payment on "
          "absence of services at VHND in the last month."),
         'beneficiaries'),
        ('eligible',
         _("Total Eligible For Payment"),
        _("Number of beneficiaries eligilble for monthly cash payment."),
         'beneficiaries'),
        ('total_payment',
         _("Total Payment"),
        _("Total Monthly cash payment made to beneficiaries"),
         'no_denom'),
        ('preg_vhnd',
         _("Pregnant VHND Attendance"),
         _("Pregnant women who attended a VHND this month or were or exempt.  "
           "Beneficiaries are exempt during the 9th month of pregancy, and when "
           "there is no VHND"),
         'pregnancies'),
        ('child_vhnd',
         _("Child VHND Attendance"),
         _("New mothers who attended a VHND this month or were exempt.  "
           "Beneficiaries are exempt during the 1st month after childbirth, "
           "and when there is no VHND"),
         'mothers'),
        ('beneficiary_vhnd',
         _("Beneficiary VHND Attendance"),
         _("Total beneficiaries who attended a VHND this month or were exempt.  "
           "Beneficiaries are exempt during the 1st month after childbirth, "
           "and when there is no VHND"),
         'beneficiaries'),
        ('ifa_tablets',
         _("IFA Receipts"),
         _("Women 6 months pregnant who have received IFA tablets.  Exempt "
           "if IFA tablets were not available."),
         'preg_6_months'),
        ('preg_weighed',
         _("Pregnancy Weight Monitoring"),
         _("Women 6 or 9 months pregnant whose weight gain was monitored this trimester.  Exempt if no VHND."),
         'preg_6_or_9_months'),
        ('child_weighed',
         _("Child Weight Monitoring"),
         _("3-month-old children who have been weighed since birth"),
         'child_3_months'),
        ('children_registered',
         _("Births Registered"),
         _("6-month-old children whose birth was registered.  Exempt if no VHND."),
         'child_6_months'),
        ('child_growth_monitored',
         _("Child Growth Monitored"),
        _("Number of children whose age is a multiple of 3 months who have "
          "attended at least one growth monitoring session in the last 3 "
          "months.  Exempt if no scale was available at the VHND."),
         'child_mult_3_months'),
        ('ors_received',
         _("ORS received"),
         _("Number of children who contracted diarrhea and received ORS and "
           "Zinc treatment."),
         'has_diarhea'),
        ('child_breastfed',
         _("Children Breastfed"),
         _("Number of Children 6 months old reported to have exclusively breastfed"),
         'child_6_months'),
        ('measles_vaccine',
         _("Measles Vaccine"),
        _("Number of children 12 months of age who have received measles "
          "vaccine.  Exempt if no vaccine was available."),
         'child_12_months'),
        ('vhnd_held',
         _("VHND"),
         _("VHND organized at AWC"),
         'no_denom'),
        ('adult_scale_available',
         _("Adult Weighing Machine Available"),
         _("Adult weighing machine available at vhnd"),
         'no_denom'),
        ('adult_scale_functional',
         _("Adult Weighing Machine Functional"),
         _("Adult weighing machine functional at vhnd"),
         'no_denom'),
        ('child_scale_available',
         _("Child Weighing Machine Available"),
         _("Child weighing machine available at vhnd"),
         'no_denom'),
        ('child_scale_functional',
         _("Child Weighing Machine Functional"),
         _("Child weighing machine functional at vhnd"),
         'no_denom'),
        ('anm_present',
         _("ANM Present"),
         _("ANM Present at VHND"),
         'no_denom'),
        ('asha_present',
         _("ASHA Present"),
         _("ASHA Present at VHND"),
         'no_denom'),
        ('cmg_present',
         _("CMG Present"),
         _("CMG Present at VHND"),
         'no_denom'),
        ('ifa_stock_available',
         _("Stock of IFA tablets"),
         _("AWC has enough Stock of IFA tablets"),
         'no_denom'),
        ('ors_stock_available',
         _("Stock of ORS packets"),
         _("AWC has enough Stock of ORS packets"),
         'no_denom'),
        ('zinc_stock_available',
         _("Stock of ZINC tablets"),
         _("AWC has enough Stock of ZINC tablets"),
         'no_denom'),
        ('measles_stock_available',
         _("Stock of Measles Vaccine"),
         _("AWC has enough Stock of Measles Vaccine"),
         'no_denom'),
        ('birth_spacing_bonus',
         _("Eligilble for Birth Spacing bonus"),
         _("Number of Beneficiaries eligilble for Birth Spacing bonus"),
         'beneficiaries'),
        ('nutritional_bonus',
         _("Eligilble for Nutritional status bonus"),
         _("Number of Beneficiaries eligilble for Nutritional status bonus"),
         'beneficiaries'),
        ('closed_pregnants',
         _("Pregnants closed this month"),
         _("Number of Pregnant women closed this month"),
         'beneficiaries'),
        ('closed_mothers',
         _("Mothers closed this month"),
         _("Number of Mothers closed this month"),
         'mothers'),
        ('closed_children',
         _("Children closed this month"),
         _("Number of Children closed this month"),
         'children'),
        # ('',
         # _(""),
        # _(""),
         # ''),
    ]

    # TODO possible general approach in the future:
    # subclass OPMCaseRow specifically for this report, and add in indicators to
    # our hearts' content.  This would allow us to override definitions of
    # indicators based on their meanings in THIS report.
    def __init__(self, awc_name, cases):
        # Some of the cases are second or third children of the same mother
        # include that distinction here
        self.all_cases = cases
        self.primary_cases = [c for c in cases if not c.is_secondary]
        self.awc_name = awc_name

    @property
    def no_denom(self):
        return None

    @property
    @memoized
    def beneficiaries(self):
        # if len(self.all_cases) != self.pregnancies + self.children:
            # raise ValueError("Hey wait a sec, that doesn't make sense!")
        return len(self.all_cases)

    @property
    @memoized
    def pregnancies(self):
        return len([c for c in self.all_cases if c.status == 'pregnant'])

    @property
    @memoized
    def mothers(self):
        return len([c for c in self.primary_cases if c.status == 'mother'])

    @property
    def children(self):
        return sum([c.num_children for c in self.primary_cases])

    @property
    @memoized
    def eligible_by_fulfillment(self):
        return len([c for c in self.all_cases
                    if c.vhnd_available and c.all_conditions_met])

    @property
    @memoized
    def eligible_by_default(self):
        return len([c for c in self.all_cases
                    if not c.vhnd_available and c.all_conditions_met])

    @property
    def eligible(self):
        return self.eligible_by_default + self.eligible_by_fulfillment

    @property
    def total_payment(self):
        return sum([c.cash_amt for c in self.all_cases])

    @property
    def preg_vhnd(self):
        return len([c for c in self.all_cases if c.preg_attended_vhnd])

    @property
    def child_vhnd(self):
        return len([c for c in self.all_cases if c.child_attended_vhnd])

    @property
    def beneficiary_vhnd(self):
        return len([c for c in self.all_cases if c.child_attended_vhnd or c.preg_attended_vhnd])

    @property
    def ifa_tablets(self):
        return len([c for c in self.all_cases if c.preg_received_ifa])

    @property
    def preg_6_months(self):
        return len([c for c in self.all_cases if c.preg_month == 6])

    @property
    def preg_6_or_9_months(self):
        return len([c for c in self.all_cases if c.preg_month in (6, 9)])

    @property
    def preg_weighed(self):
        return len([c for c in self.all_cases if c.preg_weighed])

    @property
    def child_weighed(self):
        return len([c for c in self.all_cases if c.child_weighed_once])

    @property
    def child_3_months(self):
        return len([c for c in self.all_cases if c.child_age == 3])

    @property
    def ors_received(self):
        return len([c for c in self.all_cases if c.child_with_diarhea_received_ors])

    @property
    def has_diarhea(self):
        return len([c for c in self.all_cases if c.child_has_diarhea])

    @property
    def children_registered(self):
        return len([c for c in self.all_cases if c.child_birth_registered])

    @property
    def child_6_months(self):
        return len([c for c in self.all_cases if c.child_age == 6])

    @property
    def child_growth_monitored(self):
        return len([c for c in self.all_cases if c.child_growth_calculated])

    @property
    def child_mult_3_months(self):
        # number of children whose age is a multiple of 3 months
        return len([c for c in self.all_cases
                    if c.child_age and c.child_age % 3 == 0])

    @property
    def child_breastfed(self):
        return len([c for c in self.all_cases if c.child_breastfed])

    @property
    def measles_vaccine(self):
        return len([c for c in self.all_cases if c.child_received_measles_vaccine])

    @property
    def child_12_months(self):
        return len([c for c in self.all_cases if c.child_age == 12])

    @property
    def vhnd_held(self):
        return 1 if self.all_cases and self.all_cases[0].vhnd_available else 0

    def service_available(self, service):
        return (1 if self.all_cases and
                self.all_cases[0].is_service_available(service, 1) else 0)

    @property
    def anm_present(self):
        return self.service_available('attend_ANM')

    @property
    def asha_present(self):
        return self.service_available('attend_ASHA')

    @property
    def cmg_present(self):
        return self.service_available('attend_cmg')

    @property
    def adult_scale_available(self):
        return self.service_available('big_weight_machine_avail')

    @property
    def adult_scale_functional(self):
        return self.service_available('func_bigweighmach')

    @property
    def child_scale_available(self):
        return self.service_available('child_weight_machine_avail')

    @property
    def child_scale_functional(self):
        return self.service_available('func_childweighmach')

    @property
    def ifa_stock_available(self):
        return self.service_available('stock_ifatab')

    @property
    def ors_stock_available(self):
        return self.service_available('stock_ors')

    @property
    def zinc_stock_available(self):
        return self.service_available('stock_zntab')

    @property
    def measles_stock_available(self):
        return self.service_available('stock_measlesvacc')

    @property
    def birth_spacing_bonus(self):
        return len([c for c in self.all_cases if c.birth_spacing_years])

    @property
    def nutritional_bonus(self):
        return len([c for c in self.all_cases if c.weight_grade_normal])

    @property
    def closed_pregnants(self):
        return len([c for c in self.all_cases if c.status == 'pregnant' and c.closed_in_reporting_month])

    @property
    def closed_mothers(self):
        return len([c for c in self.primary_cases if c.status == 'mother' and c.closed_in_reporting_month])

    @property
    def closed_children(self):
        return sum([c.num_children for c in self.primary_cases
                    if c.status == 'mother' and c.closed_in_reporting_month])
