from numbers import Number


def calc_percentage(num, denom):
    if isinstance(num, Number) and isinstance(denom, Number):
        if denom != 0:
            return num * 100 / denom
        else:
            return 0
    else:
            return 0


def format_percent(value, percent):

    if not isinstance(value, Number):
        value = 0

    if percent < 33:
        color = 'red'
    elif 33 <= percent <= 67:
        color = 'orange'
    else:
        color = 'green'
    return "<span style='display: block; text-align:center; color:%s;'>%d<hr style='margin: 0;border-top: 0; border-color: black;'>%d%%</span>" % (color, value, percent)


def normal_format(value):
    if not value:
        value = 0
    return "<span style='display: block; text-align:center;'>%d<hr style='margin: 0;border-top: 0; border-color: black;'></span>" % value


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
        ('children_was_registered', "# of Children Whose Birth Was Registered"),
        ('grow_1_session', "# of Children Who Have Attended At Least 1 Growth Monitoring Session"),
        ('grow_2_session', "# of Children Who Have Attended At Least 2 Growth Monitoring Sessions"),
        ('grow_3_session', "# of Children Who Have Attended At Least 3 Growth Monitoring Sessions"),
        ('grow_4_session', "# of Children Who Have Attended At Least 4 Growth Monitoring Sessions"),
        ('grow_5_session', '# of Children Who Have Attended At Least 5 Growth Monitoring Sessions'),
        ('grow_6_session', '# of Children Who Have Attended At Least 6 Growth Monitoring Sessions'),
        ('grow_7_session', '# of Children Who Have Attended At Least 7 Growth Monitoring Sessions'),
        ('grow_8_session', '# of Children Who Have Attended At Least 8 Growth Monitoring Sessions'),
        ('grow_9_session', '# of Children Who Have Attended At Least 9 Growth Monitoring Sessions'),
        ('grow_10_session', '# of Children Who Have Attended At Least 10 Growth Monitoring Sessions'),
        ('grow_11_session', '# of Children Who Have Attended At Least 11 Growth Monitoring Sessions'),
        ('grow_12_session', '# of Children Who Have Attended At Least 12 Growth Monitoring Sessions'),
        ('nutritional_status_normal', '# of Children Whose Nutritional Status is Normal'),
        ('nutritional_status_mam', '# of Children Whose Nutritional Status is "MAM"'),
        ('nutritional_status_sam', '# of Children Whose Nutritional Status is "SAM"'),
        ('ors_zinc', '# of Children Who Have Received ORS and Zinc Treatment if He/She Contracts Diarrhea'),
        ('breastfed', '# of Lactating Mothers Who Reported to Have Exclusively Breastfed Their Children for First 6 Months'),
        ('measles_vaccine', '# of Children Who Received Measles Vaccine'),
    ]




    def __init__(self, worker, report, sql_data=None):

        # make sure worker passes the filters
        report.filter(
            lambda key: worker.user_data.get(key),
            # user.awc, user.block
            [('awc', 'awcs'), ('block', 'blocks')]
        )

        self.awc = worker.user_data.get('awc', "Invalid AWC name")
        if sql_data:
            ben = sql_data.get('beneficiaries_registered_total', 0)
            child_num = sql_data.get('children_total', 0)
            mother_num = sql_data.get('lactating_total', 0)
            self.beneficiaries_registered = normal_format(ben)
            self.pregnant_women = format_percent(sql_data.get('lmp_total', 0), calc_percentage(sql_data.get('lmp_total', 0), ben))
            self.mother = format_percent(mother_num, calc_percentage(mother_num, ben))
            self.children = normal_format(child_num)
            self.vhnd_monthly = format_percent(sql_data.get('vhnd_monthly_total', 0), calc_percentage(sql_data.get('vhnd_monthly_total', 0), ben))
            self.ifa_tablets = format_percent(sql_data.get('ifa_tablets_total', 0), calc_percentage(sql_data.get('ifa_tablets_total', 0), ben))
            self.weight_once = format_percent(sql_data.get('weight_once_total', 0), calc_percentage(sql_data.get('weight_once_total', 0), ben))
            self.weight_twice = format_percent(sql_data.get('weight_twice_total', 0), calc_percentage(sql_data.get('weight_twice_total', 0), ben))
            self.children_weight = format_percent(sql_data.get('children_monitored_at_birth_total', 0), calc_percentage(sql_data.get('children_monitored_at_birth_total', 0), child_num))
            self.children_was_registered = format_percent(sql_data.get('children_registered_total', 0), calc_percentage(sql_data.get('children_registered_total', 0), child_num))
            self.grow_1_session = format_percent(sql_data.get('growth_monitoring_session_1', 0), calc_percentage(sql_data.get('growth_monitoring_session_1', 0), child_num))
            self.grow_2_session = format_percent(sql_data.get('growth_monitoring_session_2', 0), calc_percentage(sql_data.get('growth_monitoring_session_2', 0), child_num))
            self.grow_3_session = format_percent(sql_data.get('growth_monitoring_session_3', 0), calc_percentage(sql_data.get('growth_monitoring_session_3', 0), child_num))
            self.grow_4_session = format_percent(sql_data.get('growth_monitoring_session_4', 0), calc_percentage(sql_data.get('growth_monitoring_session_4', 0), child_num))
            self.grow_5_session = format_percent(sql_data.get('growth_monitoring_session_5', 0), calc_percentage(sql_data.get('growth_monitoring_session_5', 0), child_num))
            self.grow_6_session = format_percent(sql_data.get('growth_monitoring_session_6', 0), calc_percentage(sql_data.get('growth_monitoring_session_6', 0), child_num))
            self.grow_7_session = format_percent(sql_data.get('growth_monitoring_session_7', 0), calc_percentage(sql_data.get('growth_monitoring_session_7', 0), child_num))
            self.grow_8_session = format_percent(sql_data.get('growth_monitoring_session_8', 0), calc_percentage(sql_data.get('growth_monitoring_session_8', 0), child_num))
            self.grow_9_session = format_percent(sql_data.get('growth_monitoring_session_9', 0), calc_percentage(sql_data.get('growth_monitoring_session_9', 0), child_num))
            self.grow_10_session = format_percent(sql_data.get('growth_monitoring_session_10', 0), calc_percentage(sql_data.get('growth_monitoring_session_10', 0), child_num))
            self.grow_11_session = format_percent(sql_data.get('growth_monitoring_session_11', 0), calc_percentage(sql_data.get('growth_monitoring_session_11', 0), child_num))
            self.grow_12_session = format_percent(sql_data.get('growth_monitoring_session_12', 0), calc_percentage(sql_data.get('growth_monitoring_session_12', 0), child_num))
            self.nutritional_status_normal = format_percent(sql_data.get('nutritional_status_normal_total', 0), calc_percentage(sql_data.get('nutritional_status_normal_total', 0), child_num))
            self.nutritional_status_mam = format_percent(sql_data.get('nutritional_status_mam_total', 0), calc_percentage(sql_data.get('nutritional_status_mam_total', 0), child_num))
            self.nutritional_status_sam = format_percent(sql_data.get('nutritional_status_sam_total', 0), calc_percentage(sql_data.get('nutritional_status_sam_total', 0), child_num))

            treated = sql_data.get('treated_total', 0)
            suffering = sql_data.get('suffering_total', 0)

            self.ors_zinc = format_percent(treated, calc_percentage(treated, suffering))
            self.breastfed = format_percent(sql_data.get('excbreastfed_total', 0), calc_percentage(sql_data.get('excbreastfed_total', 0), mother_num))
            self.measles_vaccine = format_percent(sql_data.get('measlesvacc_total', 0), calc_percentage(sql_data.get('measlesvacc_total', 0), child_num))
        else:
            self.beneficiaries_registered = format_percent(0, 0)
            self.pregnant_women = format_percent(0, 0)
            self.mother = format_percent(0, 0)
            self.children = format_percent(0, 0)
            self.vhnd_monthly = format_percent(0, 0)
            self.ifa_tablets = format_percent(0, 0)
            self.weight_once = format_percent(0, 0)
            self.weight_twice = format_percent(0, 0)
            self.children_weight = format_percent(0, 0)
            self.children_was_registered = format_percent(0, 0)
            self.grow_1_session = format_percent(0, 0)
            self.grow_2_session = format_percent(0, 0)
            self.grow_3_session = format_percent(0, 0)
            self.grow_4_session = format_percent(0, 0)
            self.grow_5_session = format_percent(0, 0)
            self.grow_6_session = format_percent(0, 0)
            self.grow_7_session = format_percent(0, 0)
            self.grow_8_session = format_percent(0, 0)
            self.grow_9_session = format_percent(0, 0)
            self.grow_10_session = format_percent(0, 0)
            self.grow_11_session = format_percent(0, 0)
            self.grow_12_session = format_percent(0, 0)
            self.nutritional_status_normal = format_percent(0, 0)
            self.nutritional_status_mam = format_percent(0, 0)
            self.nutritional_status_sam = format_percent(0, 0)
            self.ors_zinc = format_percent(0, 0)
            self.breastfed = format_percent(0, 0)
            self.measles_vaccine = format_percent(0, 0)
