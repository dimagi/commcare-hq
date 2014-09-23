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
