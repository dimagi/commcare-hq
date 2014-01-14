import re
from datetime import datetime, date, timedelta

from couchdbkit.exceptions import ResourceNotFound

from .constants import *
from .models import OpmCaseFluff, OpmUserFluff, OpmFormFluff


class HealthStatus(object):

    # maps method name to header
    method_map = [
        ('awc', "AWC"),
        ('beneficiaries_registered', "Total # of Beneficiaries Registered"),
        ('pregnant_women', "# of Pregnant Women Registered"),
        ('mother', "# of Lactating Mothers Registered"),
        ('children', "# of Children Between 0 and 3 Years of Age Registered"),
        ('vhnd_monthly', "# of Beneficiaries Attending VHND Monthly"),
        ('ifa_tablets', "# of Pregnant Women Who Have Received at least 30 IFA Tablets"),
        ('weight_once', "# of Pregnant Women Whose Weight Gain Was Monitored At Least Once"),
        ('weight_twice', "# of Pregnant Women Whose Weight Gain Was Monitored Twice"),
        ('children_weight', "# of Children Whose Weight Was Monitored at Birth"),
        ('children_was_registred', "# of Children Whose Birth Was Registered"),
        ('grow_1_session', "# of Children Who Have Attended At Least 1 Growth Monitoring Session"),
        ('grow_2_session', "# of Children Who Have Attended At Least 2 Growth Monitoring Sessions"),
        ('grow_3_session', "# of Children Who Have Attended At Least 3 Growth Monitoring Sessions"),
        ('grow_5_session', "# of Children Who Have Attended At Least 4 Growth Monitoring Sessions"),
        ('grow_6_session', '# of Children Who Have Attended At Least 5 Growth Monitoring Sessions'),
        ('grow_7_session', '# of Children Who Have Attended At Least 6 Growth Monitoring Sessions'),
        ('grow_8_session', '# of Children Who Have Attended At Least 7 Growth Monitoring Sessions'),
        ('grow_9_session', '# of Children Who Have Attended At Least 8 Growth Monitoring Sessions'),
        ('grow_10_session', '# of Children Who Have Attended At Least 9 Growth Monitoring Sessions'),
        ('grow_11_session', '# of Children Who Have Attended At Least 10 Growth Monitoring Sessions'),
        ('grow_12_session', '# of Children Who Have Attended At Least 11 Growth Monitoring Sessions'),
        ('grow_13_session', '# of Children Who Have Attended At Least 12 Growth Monitoring Sessions'),
        ('nutritional_status_normal', '# of Children Whose Nutritional Status is Normal'),
        ('nutritional_status_mam', '# of Children Whose Nutritional Status is "MAM"'),
        ('nutritional_status_sam', '# of Children Whose Nutritional Status is "SAM"'),
        ('ors_zinc', '# of Children Who Have Received ORS and Zinc Treatment if He/She Contracts Diarrhea'),
        ('breastfed', '# of Lactating Mothers Who Reported to Have Exclusively Breastfed Their Children for First 6 Months'),
        ('measles_vaccine', '# of Children Who Received Measles Vaccine'),
    ]
