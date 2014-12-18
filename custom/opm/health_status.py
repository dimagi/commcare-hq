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
        # method, header, count_method
        ('awc_name', _("AWC Name"), 'no_denom'),
        ('beneficiaries', _("Total Beneficiaries"), 'no_denom'),
        ('pregnancies', _("Pregnant Women"), 'beneficiaries'),
        ('mothers', _("Mothers of Children Aged 3 Years and Below"), 'beneficiaries'),
        ('children', _("Children Between 0 and 3 Years of Age"), 'beneficiaries'),
        ('vhnd_monthly', _("Beneficiaries Attending VHND Monthly"), 'Beneficiaries'),
        ('ifa_tablets', _("Pregnant Women Who Have Received at least 30 IFA Tablets"), 'no_denom'),
        ('preg_weighed', _("Pregnant Women Whose Weight Gain Was Monitored"), 'no_denom'),
        ('child_weighed', _("Children Whose Weight Was Monitored"), 'no_denom'),
        ('children_registered', _("Children Whose Birth Was Registered"), 'no_denom'),
    ]
    # TODO possible general approach in the future:
    # subclass OPMCaseRow specifically for this report, and add in indicators to
    # our hearts' content
    def __init__(self, cases):
        self.cases = cases
        self.awc_name = cases[0].awc_name

    @property
    def no_denom(self):
        return None

    @property
    @memoized
    def beneficiaries(self):
        return len(self.cases)

    @property
    def pregnancies(self):
        return len([c for c in self.cases if c.status == 'pregnant'])

    @property
    def mothers(self):
        return len([c for c in self.cases if c.status == 'mother'])

    @property
    def children(self):
        return sum([c.num_children for c in self.cases])

    @property
    def vhnd_monthly(self):
        # TODO in preg month 9 and child month 1 this condition is always met.
        # TODO counts as yes if VHND was not available
        # Include that or not?
        return len([c for c in self.cases
                    if c.preg_attended_vhnd or c.child_attended_vhnd])

    @property
    def ifa_tablets(self):
        # TODO this is only relevant for women in their 6th month of pregnancy
        # TODO counts as yes if VHND was not available
        return len([c for c in self.cases if c.preg_received_ifa])

    @property
    def preg_weighed(self):
        # TODO only counts months 6 and 9
        # TODO counts as yes if VHND was not available
        return len([c for c in self.cases if c.preg_weighed])

    @property
    def child_weighed(self):
        # TODO only counts when child_age == 3
        return len([c for c in self.cases if c.child_weighed_once])

    @property
    def children_registered(self):
        # TODO only counts at child_age == 6
        # TODO counts as yes if VHND was not available
        return len([c for c in self.cases if c.child_birth_registered])
