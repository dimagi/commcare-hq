from collections import defaultdict
from datetime import datetime
from typing import Dict, Iterator, List

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
from custom.abt.reports.filters_2020 import (
    LevelFourFilter,
    LevelOneFilter,
    LevelThreeFilter,
    LevelTwoFilter,
    SubmissionStatusFilter,
)
from custom.abt.reports.fixture_utils import get_locations

INDICATORS_FORM_XMLNS = 'http://openrosa.org/formdesigner/00CEB41B-2967-4370-9EA3-BFD9BD7AF785'


class LatePmt2020Report(GenericTabularReport, CustomProjectReport, DatespanMixin):
    report_title = "Late PMT"
    slug = 'late_pmt_2020'
    name = "Late PMT 2020"

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
    def pmts_submitted_by_date(self) -> Dict[datetime.date, set]:
        pmts_submitted = defaultdict(set)
        forms = iter_forms_by_xmlns_received_on(
            self.domain, INDICATORS_FORM_XMLNS, self.startdate, self.enddate
        )
        for form in forms:
            cases = get_cases_from_forms(self.domain, [form])
            location_ids = {c.operation_site for c in cases}
            pmts_submitted[form.received_on.date()].update(location_ids)
        return pmts_submitted

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

        show_all = self.report_config['submission_status'] != 'missing_pmt_data'
        dates = rrule(
            DAILY,
            dtstart=self.startdate,
            until=self.enddate,
            byweekday=(MO, TU, WE, TH, FR, SA)
        )
        rows = []
        for date in dates:
            for location in get_locations(self.domain, self.report_config):
                pmt_submitted = location.id in self.pmts_submitted_by_date[date.date()]
                error_msg = '' if pmt_submitted else _('Incorrect or no PMT data submitted')
                if show_all or not pmt_submitted:
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
