from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, DataTablesColumnGroup
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import CustomProjectReport
from custom.up_nrhm.filters import NRHMDatespanMixin
from custom.up_nrhm.sql_data import ASHAFunctionalityChecklistData, ASHAAFChecklistData
from dimagi.utils.dates import force_to_datetime
from django.utils.translation import ugettext as _, ugettext_noop


class ASHAFunctionalityChecklistReport(GenericTabularReport, NRHMDatespanMixin, CustomProjectReport):
    name = ugettext_noop("Format-1 for ASHA Sanginis")
    slug = "asha_functionality_checklist_report"

    @property
    def report_config(self):
        return {
            'domain': self.domain,
            'startdate': self.datespan.startdate,
            'enddate': self.datespan.enddate.replace(hour=23, minute=59, second=59),
            'af': self.request.GET.get('hierarchy_af'),
            'is_checklist': 1
        }

    @property
    def model_data(self):
        return ASHAFunctionalityChecklistData(config=self.report_config)

    @property
    def ashas(self):
        return sorted(self.model_data.data.values(), key=lambda x: x['completed_on'])

    @property
    def headers(self):
        headers = DataTablesHeader(*[
            DataTablesColumn('', sortable=False, sort_type="title-numeric"),
            DataTablesColumnGroup(_('ASHAs'), DataTablesColumn(_('Name of ASHAs'), sortable=False)),
        ])

        for index, v in enumerate(self.ashas):
            headers.add_column(DataTablesColumnGroup(index + 1,
                                                     DataTablesColumn(v['hv_asha_name'], sortable=False)))
        headers.add_column(DataTablesColumn('', sortable=False))
        return headers

    @property
    def rows(self):
        default_row_data = [
            ['', _('Date when cheklist was filled')],
            [1, _('Newborn visits within first day of birth in case of home deliveries')],
            [2, _('Set of home visits for newborn care as specified in the HBNC guidelines '
                  '(six visits in case of Institutional delivery and seven in case of a home delivery)')],
            [3, _('Attending VHNDs/Promoting immunization')],
            [4, _('Supporting institutional delivery')],
            [5, _('Management of childhood illness - especially diarrhea and pneumonia')],
            [6, _('Household visits with nutrition counseling')],
            [7, _('Fever cases seen/malaria slides made in malaria endemic area')],
            [8, _('Acting as DOTS provider')],
            [9, _('Holding or attending village/VHSNC meeting')],
            [10, _('Successful referral of the IUD, female sterilization or male '
                   'sterilization cases and/or providing OCPs/Condoms')],
            ['', _('Total of number of tasks on which ASHA reported being functional')],
            ['', _('Total number of ASHAs who are functional on at least %s of the tasks' % '60%')],
            ['', _('Remark')]
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
                domain=self.domain,
                is_checklist=1
            )).data
            total = 0
            denominator = 0
            for idx, p in enumerate(properties):
                if data[p] == 1:
                    ttotal[idx] += 1
                    total += 1
                if p != 'completed_on' and data[p] != 88:
                    denominator += 1
                if p == 'completed_on':
                    default_row_data[idx].append(data[p].strftime('%Y-%m-%d %H:%M'))
                else:
                    default_row_data[idx].append(data[p] if data[p] != 88 else 'NA')
            try:
                percent = total * 100 / denominator
            except ZeroDivisionError:
                percent = 0
            if percent >= 60:
                total_of_functional += 1
            default_row_data[-3].append(total)
            default_row_data[-2].append('{0}/{1} ({2}%)'.format(total, denominator, percent))
            default_row_data[-1].append('')

        for idx, row in enumerate(default_row_data):
            if idx == 0:
                row.append(_('Total no. of ASHAs functional on each tasks'))
            elif 0 < idx < 11:
                row.append(ttotal[idx])
            elif idx == 12:
                row.append(total_of_functional)
            else:
                row.append('')

        return default_row_data
