from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.sqlreport import DataFormatter, TableDataFormat
from corehq.apps.reports.standard import CustomProjectReport, DatespanMixin
from corehq.apps.reports.filters.dates import DatespanFilter
from custom.up_nrhm.filters import DrillDownOptionFilter
from custom.up_nrhm.sql_data import ASHAFacilitatorsData


class ASHAFacilitatorsReport(GenericTabularReport, DatespanMixin, CustomProjectReport):
    fields = [DatespanFilter, DrillDownOptionFilter]
    name = "ASHA Facilitators Report"
    slug = "asha_facilitators_report"
    show_all_rows = True
    default_rows = 20
    use_datatables = False
    printable = True
    base_template = "up_nrhm/asha_report.html"

    LEFT_COLUMN_NAMES = [
        "Newborn visits within first day of birth in case of home deliveries",
        "Set of home visits for newborn care as specified in the HBNC guidelines "
        "(six visits in case of Institutional delivery and seven in case of a home delivery)",
        "Attending VHNDs/Promoting immunization",
        "Supporting institutional delivery",
        "Management of childhood illness - especially diarrhea and pneumonia",
        "Household visits with nutrition counseling",
        "Fever cases seen/malaria slides made in malaria endemic area",
        "Acting as DOTS provider",
        "Holding or attending village/VHSNC meeting",
        "Successful referral of the IUD, "
        "Female sterilization or male sterilization cases and/or providing OCPs/Condoms",
        "Total number of ASHAs who are functional on at least 6/10 tasks"
    ]

    @property
    def report_config(self):
        return {
            'domain': self.domain,
            'startdate': self.datespan.startdate,
            'enddate': self.datespan.enddate,
            'startdate_str': str(self.datespan.startdate),
            'enddate_str': str(self.datespan.enddate),
            'af': self.request.GET.get('hierarchy_af'),
            'count_one': 1,
            'sixty_percents': 60,
        }

    @property
    def model(self):
        return ASHAFacilitatorsData(config=self.report_config)

    @property
    def headers(self):
        return DataTablesHeader()

    @property
    def rows(self):
        no_value = dict(sort_key=0L, html=0L)
        model = self.model
        formatter = DataFormatter(TableDataFormat(model.columns, no_value=no_value))
        rows = list(formatter.format(model.data, keys=model.keys, group_by=model.group_by))
        if not rows:
            return []

        assert len(rows) == 1
        row = [row.get('sort_key') or 0L for row in rows[0]]
        all_ashas = row[0]
        all_ashas_with_checklist = row[1]
        headers = [
            ['Total number of ASHAs under the Facilitator', '', all_ashas, ''],
            ['Total number of ASHAs for whom the functionality checklist was filled',
             '', all_ashas_with_checklist, ''],
            ["", "Total no. of ASHAs functional", "Total no. of ASHAs who did not report/not known", "Rmarks"]
        ]
        return headers + [
            [self.LEFT_COLUMN_NAMES[idx], element, all_ashas - all_ashas_with_checklist, '']
            for idx, element in enumerate(row[2:])
        ]
