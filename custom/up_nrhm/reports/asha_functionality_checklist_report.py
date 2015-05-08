from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, DataTablesColumnGroup
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import CustomProjectReport
from custom.up_nrhm.filters import NRHMDatespanMixin
from custom.up_nrhm.sql_data import ASHAFunctionalityChecklistData, ASHAAFChecklistData
from dimagi.utils.dates import force_to_datetime


class ASHAFunctionalityChecklistReport(GenericTabularReport, NRHMDatespanMixin, CustomProjectReport):
    name = "ASHA Functionality Checklist Report"
    slug = "asha_functionality_checklist_report"

    @property
    def report_config(self):
        return {
            'domain': self.domain,
            'startdate': self.datespan.startdate,
            'enddate': self.datespan.enddate,
            'af': self.request.GET.get('hierarchy_af'),
        }

    @property
    def model_data(self):
        return ASHAFunctionalityChecklistData(config=self.report_config)

    @property
    def ashas(self):
        return sorted(self.model_data.data.values(), key=lambda x: x['hv_asha_name'])

    @property
    def headers(self):
        headers = DataTablesHeader(*[
            DataTablesColumn('', sortable=False, sort_type="title-numeric"),
            DataTablesColumnGroup('ASHAs', DataTablesColumn('Name of ASHAs', sortable=False)),
        ])

        for index, v in enumerate(self.ashas):
            headers.add_column(DataTablesColumnGroup(index + 1,
                                                     DataTablesColumn(v['hv_asha_name'], sortable=False)))
        headers.add_column(DataTablesColumn('', sortable=False))
        return headers

    @property
    def rows(self):
        default_row_data = [
            ['', 'Date when cheklist was filled'],
            [1, 'Newborn visits within first day of birth in case of home deliveries'],
            [2, 'Set of home visits for newborn care as specified in the HBNC guidelines (six '
                'visits in case of Institutional delivery and seven in case of a home delivery)'],
            [3, 'Attending VHNDs/Promoting immunization'],
            [4, 'Supporting institutional delivery'],
            [5, 'Management of childhood illness - especially diarrhea and pneumonia'],
            [6, 'Household visits with nutrition counseling'],
            [7, 'Fever cases seen/malaria slides made in malaria endemic area'],
            [8, 'Acting as DOTS provider'],
            [9, 'Holding or attending village/VHSNC meeting'],
            [10, 'Successful referral of the IUD, female sterilization or male '
                 'sterilization cases and/or providing OCPs/Condoms'],
            ['', 'Total of number of tasks on which ASHA reported being functional'],
            ['', 'Total number of ASHAs who are functional on at least 6/10 tasks'],
            ['', 'Remark']
        ]

        properties = ['completed_on', 'hv_fx_home_birth_visits', 'hv_fx_newborns_visited', 'hv_fx_vhnd',
                      'hv_fx_support_inst_delivery', 'hv_fx_child_illness_mgmt', 'hv_fx_nut_counseling',
                      'hv_fx_malaria', 'hv_fx_dots', 'hv_fx_vhsnc', 'hv_fx_fp']

        ttotal = [0] * len(default_row_data)
        total_of_functional = 0
        for asha in self.ashas:
            data = ASHAAFChecklistData(config=dict(
                doc_id=asha['doc_id'],
                date=force_to_datetime(self.request.GET.get('date')),
                domain=self.domain
            )).data
            total = 0
            for idx, p in enumerate(properties):
                if data[p] == 1:
                    ttotal[idx] += 1
                    total += 1
                default_row_data[idx].append(data[p] if data[p] != 88 else 'NA')
            if total >= 6:
                total_of_functional += 1
            default_row_data[-3].append(total)
            default_row_data[-2].append('{0}/{1}'.format(total, 10))
            default_row_data[-1].append('')

        for idx, row in enumerate(default_row_data):
            if idx == 0:
                row.append('Total no. of ASHAs functional on each tasks')
            elif 0 < idx < 11:
                row.append(ttotal[idx])
            elif idx == 12:
                row.append(total_of_functional)
            else:
                row.append('')

        return default_row_data
