from datetime import datetime
from typing import Iterator, List

from django.db.models import Q
from django.utils.functional import cached_property
from django.utils.translation import ugettext as _

from dateutil.rrule import DAILY, FR, MO, SA, TH, TU, WE, rrule

from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader
from corehq.apps.reports.filters.dates import DatespanFilter
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import CustomProjectReport, DatespanMixin
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.models import CommCareCaseSQL, XFormInstanceSQL
from custom.abt.reports.filters import (
    LevelFourFilter,
    LevelOneFilter,
    LevelThreeFilter,
    LevelTwoFilter,
    SubmissionStatusFilter,
)
from custom.abt.reports.fixture_utils import get_locations

INDICATORS_FORM_XMLNS = 'http://openrosa.org/formdesigner/00CEB41B-2967-4370-9EA3-BFD9BD7AF785'


class LatePmtReport(GenericTabularReport, CustomProjectReport, DatespanMixin):
    report_title = "Late PMT"
    slug = 'late_pmt'
    name = "Late PMT"

    languages = (
        'en',
        'fra',
        'por'
    )

    fields = [
        DatespanFilter,
        LevelOneFilter,
        LevelTwoFilter,
        LevelThreeFilter,
        LevelFourFilter,
        SubmissionStatusFilter,
    ]

    @property
    def report_config(self):
        return {
            'domain': self.domain,
            'startdate': self.startdate,
            'enddate': self.enddate,
            'level_1': self.request.GET.get('level_1', ''),
            'level_2': self.request.GET.get('level_2', ''),
            'level_3': self.request.GET.get('level_3', ''),
            'level_4': self.request.GET.get('level_4', ''),
            'submission_status': self.request.GET.get('submission_status', '')
        }

    @property
    def startdate(self):
        return self.request.datespan.startdate

    @property
    def enddate(self):
        return self.request.datespan.end_of_end_day

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn(_("Missing Report Date")),
            DataTablesColumn(_("Name")),
            DataTablesColumn(_("Country")),
            DataTablesColumn(_("Level 1")),
            DataTablesColumn(_("Level 2")),
            DataTablesColumn(_("Level 3")),
            DataTablesColumn(_("Level 4")),
            DataTablesColumn(_("Submission Status")),
        )

    @cached_property
    def pmts_submitted(self):
        forms = list(iter_forms_by_xmlns_received_on(
            self.domain, INDICATORS_FORM_XMLNS, self.startdate, self.enddate
        ))
        return {
            (case.received_on, case.operation_site)
            for case in get_cases_from_forms(self.domain, forms)
        }

    @property
    def rows(self):
        def _to_report_format(date, location, error_msg):
            return [
                date.strftime("%Y-%m-%d"),
                location.name,
                location.country,
                location.level_1,
                location.level_2,
                location.level_3,
                location.level_4,
                error_msg
            ]

        include_missing_pmt_data = self.report_config['submission_status'] != 'incorrect_pmt_data'
        # include_incorrect_pmt_data is no longer applicable, because an
        # invalid SMS will not result in a pmt_data case being created/updated
        include_incorrect_pmt_data = self.report_config['submission_status'] != 'missing_pmt_data'
        error_msg = _('Incorrect or no PMT data submitted')
        dates = rrule(
            DAILY,
            dtstart=self.startdate,
            until=self.enddate,
            byweekday=(MO, TU, WE, TH, FR, SA)
        )
        rows = []
        for date in dates:
            for location in get_locations(self.domain, self.report_config):
                pmt_submitted = (date.date(), location.id) in self.pmts_submitted
                if not pmt_submitted and (include_missing_pmt_data or include_incorrect_pmt_data):
                    rows.append(_to_report_format(date, location, error_msg))
        return rows


def iter_forms_by_xmlns_received_on(
    domain: str,
    xmlns: str,
    start_datetime: datetime,
    end_datetime: datetime,
) -> Iterator[XFormInstanceSQL]:
    """
    Iterates form submissions of a given ``xmlns`` from
    ``start_datetime`` (incl) to ``end_datetime`` (excl).
    """
    # ``start_datetime`` is inclusive and ``end_datetime`` is
    # exclusive so that a form submitted at midnight will be
    # returned for the day that is starting, not the day that is
    # ending. That seems to be intuitive.
    from corehq.sql_db.util import paginate_query_across_partitioned_databases

    q_expr = (
        Q(domain=domain)
        & Q(state=XFormInstanceSQL.NORMAL)
        & Q(xmlns=xmlns)
        & Q(received_on__gte=start_datetime, received_on__lt=end_datetime)
    )
    return paginate_query_across_partitioned_databases(
        XFormInstanceSQL, q_expr, load_source='forms_by_xmlns_received_on'
    )


def get_cases_from_forms(
    domain: str,
    forms: List[XFormInstanceSQL],
) -> List[CommCareCaseSQL]:
    if not forms:
        return []
    interface = FormProcessorInterface(domain)
    case_ids_to_case_update_metadata = interface.get_cases_from_forms(
        interface.casedb_cache, forms
    )
    cases = [meta.case for meta in case_ids_to_case_update_metadata.values()]
    return cases
