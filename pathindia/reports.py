from corehq.apps.reports._global import CustomProjectReport, ProjectReportParametersMixin, DatespanMixin
from dimagi.utils.couch.database import get_db

class PathIndiaKrantiReport(CustomProjectReport, ProjectReportParametersMixin, DatespanMixin):
    name = "Key Indicators"
    slug = "pathindia_key_indicators"
    fields = ['corehq.apps.reports.fields.FilterUsersField',
                'corehq.apps.reports.fields.GroupField',
                'corehq.apps.reports.fields.DatespanField']
    report_template_path = "pathindia/reports/kranti_report.html"
    flush_layout = True

    @property
    def report_context(self):
        report_data = dict()
        for user in self.users:
            key = [user.get('user_id')]
            data = get_db().view("pathindia/kranti_report",
                reduce=True,
                startkey = key+[self.datespan.startdate_param_utc],
                endkey = key+[self.datespan.enddate_param_utc]
            ).all()
            for item in data:
                report_data = self._merge_data(report_data, item.get('value', {}))

        delivery_place_total = report_data.get("antenatal", {}).get("delivery_place", {}).get("govt", 0) + \
                               report_data.get("antenatal", {}).get("delivery_place", {}).get("priv", 0)

        complications = report_data.get("postnatal", {}).get("complications", {})
        complications_total = complications.get("bleeding", 0) + \
                                complications.get("fever", 0) + \
                                complications.get("convulsions", 0)
        if "postnatal" in report_data:
            report_data["postnatal"]["complications_total"] = complications_total

        reg_preg_total = report_data.get("antenatal", {}).get("registered_preg", 0)
        anc_exam_total = report_data.get("antenatal", {}).get("anc_examination", 0)
        live_birth_total = report_data.get("intranatal", {}).get("outcome", {}).get("live_birth", 0)
        sexed_total = report_data.get("intranatal", {}).get("sex", {}).get("female", 0) +\
                      report_data.get("intranatal", {}).get("sex", {}).get("male", 0)
        hb_exam_total = report_data.get("antenatal", {}).get("stats", {}).get("hb_exam", 0)

        kranti_expected = dict(
            antenatal=dict(
                reg_place=dict(
                    govt=reg_preg_total,
                    priv=reg_preg_total
                ),
                early_registration=reg_preg_total,
                stats=dict(
                    bp=anc_exam_total,
                    weight=anc_exam_total,
                    abdominal_exam=anc_exam_total,
                    hb_exam=anc_exam_total
                ),
                hb=dict(
                    low=hb_exam_total,
                    avg=hb_exam_total,
                    high=hb_exam_total
                ),
                tt_booster=reg_preg_total,
                ifa_tabs=reg_preg_total,
                injection_syrup=reg_preg_total,
                delivery_place=dict(
                    govt=delivery_place_total,
                    priv=delivery_place_total
                )
            ),
            intranatal=dict(
                place=dict(
                    govt=live_birth_total,
                    priv=live_birth_total,
                    home=live_birth_total
                ),
                type=dict(
                    normal=live_birth_total,
                    lscs=live_birth_total,
                    forceps=live_birth_total
                ),
                sex=dict(
                    male=sexed_total,
                    female=sexed_total
                ),
                weight=dict(
                    low=live_birth_total,
                    avg=live_birth_total,
                    high=live_birth_total
                )
            ),
            postnatal=dict(
                currently_breastfeeding=live_birth_total,
                at_least_one_pnc=live_birth_total,
                no_pnc=live_birth_total,
                complications=dict(
                    bleeding=complications_total,
                    fever=complications_total,
                    convulsions=complications_total
                ),
                jsy=live_birth_total
            )
        )

        kranti_percentages = self._get_percentages(report_data, kranti_expected)
        month_reporting_range = self.datespan.enddate.strftime("%B %Y")
        if self.datespan.enddate.strftime("%B %Y") != self.datespan.startdate.strftime("%B %Y"):
            month_reporting_range = "%s to %s" % (self.datespan.startdate.strftime("%B %Y"), month_reporting_range)

        return dict(
            kranti=report_data,
            percentages=kranti_percentages,
            general_info=dict(
                total_link_workers=len(self.users),
                month_of_reporting=month_reporting_range,
                date_of_sending_report=self.datespan.enddate.strftime("%d %B %Y"),
                total_preg_women_monitored=get_db().view("pathindia/kranti_cases",
                    reduce=True
                ).first().get('value', 0),
                uhp=self.group.name if self.group else "All UHPs"
            )
        )

    def _merge_data(self, dict1, dict2):
        for key, val in dict2.items():
            if isinstance(val, dict):
                if key not in dict1:
                    dict1[key] = val
                else:
                    dict1[key] = self._merge_data(dict1[key], val)
            elif isinstance(val, int):
                if key not in dict1:
                    dict1[key] = val
                else:
                    dict1[key] += val
        return dict1

    def _get_percentages(self, data, expected,
                              compute_percent=lambda x,expected: (float(x)/expected)*100 if expected != 0 else 0):
        for key, val in expected.items():
            if isinstance(val, dict):
                self._get_percentages(data.get(key, {}), expected[key])
            elif isinstance(val, int):
                expected[key] = "%.2f%%" % compute_percent(data.get(key, 0), val)
        return expected

