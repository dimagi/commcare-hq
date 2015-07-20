from django.utils.translation import ugettext_lazy as _

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
        ('awc_code',
         _("AWC Code"),
         "",
         'no_denom'),
        ('awc_name',
         _("AWC Name"),
         "",
         'no_denom'),
        ('gp',
         _("Gram Panchayat"),
         "",
         'no_denom'),
        ('beneficiaries',
         _("Registered Beneficiaries"),
         _("Beneficiaries registered with BCSP"),
         'no_denom'),
        ('pregnancies',
         _("Registered pregnant women"),
         _("Pregnant women registered with BCSP"),
         'beneficiaries'),
        ('mothers',
         _("Registered mothers"),
         _("Mothers registered with BCSP"),
         'beneficiaries'),
        ('children',
         _("Registered children"),
         _("Children below 3 years of age registered with BCSP"),
         'beneficiaries'),
        ('eligible_by_fulfillment',
         _("Eligible for payment upon fulfillment of cash conditions"),
         _("Registered beneficiaries eligilble for cash payment for the month "
           "upon fulfillment of cash conditions"),
         'beneficiaries'),
        ('eligible_by_default',
         _("Eligible for payment upon absence of services"),
         _("Registered beneficiaries eligilble for cash payment for the month upon absence of services at VHND"),
         'beneficiaries'),
        ('eligible',
         _("Eligible for payment"),
         _("Registered beneficiaries eligilble for cash payment for the month"),
         'beneficiaries'),
        ('total_payment',
         _("Total cash payment"),
         _("Total cash payment made to registered beneficiaries for the month"),
         'no_denom'),
        ('preg_vhnd',
         _("Pregnant women attended VHND"),
         _("Registered pregnant women who attended VHND for the month"),
         'pregnancies'),
        ('child_vhnd',
         _("Children attended VHND"),
         _("Registered children below 3 years of age who attended VHND for the month"),
         'children'),
        ('beneficiary_vhnd',
         _("Beneficiaries attended VHND"),
         _("Registered beneficiaries who attended VHND for the month"),
         'beneficiaries'),
        ('ifa_tablets',
         _("Received at least 30 IFA tablets"),
         _("Registered pregnant women (6 months pregnant) who received at least "
           "30 IFA tablets in second trimester"),
         'preg_6_months'),
        ('preg_weighed_6',
         _("Weight monitored in second trimester"),
         _("Registered pregnant women (6 months pregnant) who got their weight monitored in second trimester"),
         'preg_6_months'),
        ('preg_weighed_9',
         _("Weight monitored in third trimester"),
         _("Registered pregnant women (9 months pregnant) who got their weight monitored in third trimester"),
         'preg_9_months'),
        ('child_weighed',
         _("Weight monitored at birth"),
         _("Registered children (3 months old) whose weight was monitored at birth"),
         'child_3_months'),
        ('children_registered',
         _("Child birth registered"),
         _("Registered children (6 months old) whose birth was registered in the first 6 months after birth"),
         'child_6_months'),
        ('child_growth_monitored_0_3',
         _("Growth monitoring when 0-3 months old"),
         _("Registered Children (3 months old) who have "
           "attended at least one growth monitoring session between the age 0-3 months"),
         'child_0_3_months'),
        ('child_growth_monitored_4_6',
         _("Growth Monitoring when 4-6 months old"),
         _("Registered Children (6 months old) who have "
           "attended at least one growth monitoring session between the age 4-6 months"),
         'child_4_6_months'),
        ('child_growth_monitored_7_9',
         _("Growth Monitoring when 7-9 months old"),
         _("Registered Children (9 months old) who have "
           "attended at least one growth monitoring session between the age 7-9 months"),
         'child_7_9_months'),
        ('child_growth_monitored_10_12',
         _("Growth Monitoring when 10-12 months old"),
         _("Registered Children (12 months old) who have "
           "attended at least one growth monitoring session between the age 10-12 months"),
         'child_10_12_months'),
        ('child_growth_monitored_13_15',
         _("Growth Monitoring when 13-15 months old"),
         _("Registered Children (15 months old) who have "
           "attended at least one growth monitoring session between the age 13-15 months"),
         'child_13_15_months'),
        ('child_growth_monitored_16_18',
         _("Growth Monitoring when 16-18 months old"),
         _("Registered Children (18 months old) who have "
           "attended at least one growth monitoring session between the age 16-18 months"),
         'child_16_18_months'),
        ('child_growth_monitored_19_21',
         _("Growth Monitoring when 19-21 months old"),
         _("Registered Children (21 months old) who have "
           "attended at least one growth monitoring session between the age 19-21 months"),
         'child_19_21_months'),
        ('child_growth_monitored_22_24',
         _("Growth Monitoring when 22-24 months old"),
         _("Registered Children (24 months old) who have "
           "attended at least one growth monitoring session between the age 22-24 months"),
         'child_22_24_months'),
        ('ors_received',
         _("Received ORS and Zinc treatment for diarrhoea"),
         _("Registered children who received ORS and Zinc treatment if he/she contracts diarrhoea"),
         'has_diarhea'),
        ('child_breastfed',
         _("Exclusively breastfed for first 6 months"),
         _("Registered children (6 months old) who have been exclusively breastfed for first 6 months"),
         'child_6_months'),
        ('measles_vaccine',
         _("Received Measles vaccine"),
         _("Registered children (12 months old) who have received Measles vaccine"),
         'child_12_months'),
        ('vhnd_held',
         _("VHND organised"),
         _("Whether VHND was organised at AWC for the month"),
         'one'),
        ('adult_scale_available',
         _("Adult Weighing Machine Available"),
         _("Whether adult weighing machine was available for the month"),
         'one'),
        ('adult_scale_functional',
         _("Adult Weighing Machine Functional"),
         _("Whether adult weighing machine was functional for the month"),
         'one'),
        ('child_scale_available',
         _("Child Weighing Machine Available"),
         _("Whether child weighing machine was available for the month"),
         'one'),
        ('child_scale_functional',
         _("Child Weighing Machine Functional"),
         _("Whether child weighing machine was functional for the month"),
         'one'),
        ('anm_present',
         _("ANM Present"),
         _("Whether ANM present at VHND for the month"),
         'one'),
        ('asha_present',
         _("ASHA Present"),
         _("Whether ASHA present at VHND for the month"),
         'one'),
        ('cmg_present',
         _("CMG Present"),
         _("Whether CMG present at VHND for the month"),
         'one'),
        ('ifa_stock_available',
         _("Stock of IFA tablets"),
         _("Whether AWC has enough stock of IFA tablets for the month"),
         'one'),
        ('ors_stock_available',
         _("Stock of ORS packets"),
         _("Whether AWC has enough stock of ORS packets for the month"),
         'one'),
        ('zinc_stock_available',
         _("Stock of ZINC tablets"),
         _("Whether AWC has enough stock of Zinc Tablets for the month"),
         'one'),
        ('measles_stock_available',
         _("Stock of Measles Vaccine"),
         _("Whether AWC has enough stock of measles vaccine for the month"),
         'one'),
        ('birth_spacing_bonus',
         _("Eligilble for Birth Spacing bonus"),
         _("Registered beneficiaries eligible for birth spacing bonus for the month"),
         'beneficiaries'),
        ('nutritional_status_sam',
         _("Severely underweight"),
         _("Registered children severely underweight (very low weight for age) for the month"),
         'children'),
        ('nutritional_status_mam',
         _("Underweight"),
         _("Registered children underweight (low weight for age) for the month"),
         'children'),
        ('nutritional_status_normal',
         _("Normal weight for age"),
         _("Registered children with normal weight for age for the month"),
         'children'),
        ('nutritional_bonus',
         _("Eligilble for Nutritional status bonus"),
         _("Registered beneficiaries eligible for nutritonal status bonus for the month"),
         'children'),
        ('closed_pregnants',
         _("Pregnant women cases closed"),
         _("Registered pregnant women cases closed for the month"),
         'beneficiaries'),
        ('closed_mothers',
         _("Mother cases closed"),
         _("Registered mother cases closed for the month"),
         'mothers'),
        ('closed_children',
         _("Children cases closed"),
         _("Registered children cases closed for the month"),
         'children'),
    ]

    # TODO possible general approach in the future:
    # subclass OPMCaseRow specifically for this report, and add in indicators to
    # our hearts' content.  This would allow us to override definitions of
    # indicators based on their meanings in THIS report.
    def __init__(self, cases, awc, awc_code, gp, block):
        # Some of the cases are second or third children of the same mother
        # include that distinction here
        self.all_cases = cases
        self.primary_cases = [c for c in cases if not c.is_secondary]
        self.awc_name = awc
        self.awc_code = awc_code
        self.gp = gp
        self.block = block

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
        return sum([c.raw_num_children for c in self.primary_cases])

    @property
    @memoized
    def eligible_by_fulfillment(self):
        if self.block is not None and self.block == 'Khijarsarai':
            return 'NA'
        return len([c for c in self.all_cases
                    if c.vhnd_available and c.all_conditions_met])

    @property
    @memoized
    def eligible_by_default(self):
        if self.block is not None and self.block == 'Khijarsarai':
            return 'NA'
        return len([c for c in self.all_cases
                    if not c.vhnd_available and c.all_conditions_met])

    @property
    def eligible(self):
        if self.block is not None and self.block == 'Khijarsarai':
            return 'NA'
        return self.eligible_by_default + self.eligible_by_fulfillment

    @property
    def total_payment(self):
        if self.block is not None and self.block == 'Khijarsarai':
            return 'NA'
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
    def preg_9_months(self):
        return len([c for c in self.all_cases if c.preg_month == 9])

    @property
    def preg_6_or_9_months(self):
        return len([c for c in self.all_cases if c.preg_month in (6, 9)])

    @property
    def preg_weighed_6(self):
        return len([c for c in self.all_cases if c.preg_weighed_trimestered(6)])

    @property
    def preg_weighed_9(self):
        return len([c for c in self.all_cases if c.preg_weighed_trimestered(9)])

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
    def child_growth_monitored_0_3(self):
        return len([c for c in self.all_cases if c.child_growth_calculated_in_window(3)])

    @property
    def child_0_3_months(self):
        # number of children whose age is a multiple of 3 months
        return len([c for c in self.all_cases
                    if c.child_age and c.child_age in range(0, 4)])

    @property
    def child_growth_monitored_4_6(self):
        return len([c for c in self.all_cases if c.child_growth_calculated_in_window(6)])

    @property
    def child_4_6_months(self):
        return len([c for c in self.all_cases
                    if c.child_age and c.child_age in range(4, 7)])

    @property
    def child_growth_monitored_7_9(self):
        return len([c for c in self.all_cases if c.child_growth_calculated_in_window(9)])

    @property
    def child_7_9_months(self):
        return len([c for c in self.all_cases
                    if c.child_age and c.child_age in range(7, 10)])

    @property
    def child_growth_monitored_10_12(self):
        return len([c for c in self.all_cases if c.child_growth_calculated_in_window(12)])

    @property
    def child_10_12_months(self):
        return len([c for c in self.all_cases
                    if c.child_age and c.child_age in range(10, 13)])

    @property
    def child_growth_monitored_13_15(self):
        return len([c for c in self.all_cases if c.child_growth_calculated_in_window(15)])

    @property
    def child_13_15_months(self):
        return len([c for c in self.all_cases
                    if c.child_age and c.child_age in range(13, 16)])

    @property
    def child_growth_monitored_16_18(self):
        return len([c for c in self.all_cases if c.child_growth_calculated_in_window(18)])

    @property
    def child_16_18_months(self):
        return len([c for c in self.all_cases
                    if c.child_age and c.child_age in range(16, 19)])

    @property
    def child_growth_monitored_19_21(self):
        return len([c for c in self.all_cases if c.child_growth_calculated_in_window(21)])

    @property
    def child_19_21_months(self):
        return len([c for c in self.all_cases
                    if c.child_age and c.child_age in range(19, 22)])

    @property
    def child_growth_monitored_22_24(self):
        return len([c for c in self.all_cases if c.child_growth_calculated_in_window(24)])

    @property
    def child_22_24_months(self):
        return len([c for c in self.all_cases
                    if c.child_age and c.child_age in range(22, 25)])

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
        if self.block is not None and self.block == 'Khijarsarai':
            return 'NA'
        return len([c for c in self.all_cases if c.birth_spacing_years])

    @property
    def nutritional_bonus(self):
        if self.block is not None and self.block == 'Khijarsarai':
            return 'NA'
        return len([c for c in self.all_cases if c.weight_grade_normal])

    @property
    def nutritional_status_sam(self):
        return len([c for c in self.all_cases if c.weight_grade_status('SAM')])

    @property
    def nutritional_status_mam(self):
        return len([c for c in self.all_cases if c.weight_grade_status('MAM')])

    @property
    def nutritional_status_normal(self):
        return len([c for c in self.all_cases if c.weight_grade_status('normal')])

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
