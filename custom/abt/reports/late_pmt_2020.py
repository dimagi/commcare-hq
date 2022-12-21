from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Dict, Iterator

from django.db.models import Q
from django.utils.functional import cached_property
from django.utils.translation import gettext as _

from dateutil.rrule import DAILY, FR, MO, SA, TH, TU, WE, rrule

from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader
from corehq.apps.reports.filters.dates import DatespanFilter
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import CustomProjectReport, DatespanMixin
from corehq.form_processor.models import XFormInstance
from custom.abt.reports.filters_2020 import (
    LevelFourFilter,
    LevelOneFilter,
    LevelThreeFilter,
    LevelTwoFilter,
)
from custom.abt.reports.fixture_utils import get_locations

INDICATORS_FORM_XMLNS = 'http://openrosa.org/formdesigner/00CEB41B-2967-4370-9EA3-BFD9BD7AF785'


class LatePmt2020Report(GenericTabularReport, CustomProjectReport, DatespanMixin):
    report_title = "Late PMT"
    slug = 'late_pmt_2020'
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
            self.domain, INDICATORS_FORM_XMLNS,
            midnight_starting(self.startdate),
            midnight_ending(self.enddate),
        )
        for form in forms:
            location_id = form.form_data['location_operation_site']
            pmts_submitted[form.received_on.date()].add(location_id)
        return pmts_submitted

    @property
    def rows(self):
        def _to_report_format(date_, location, error_msg):
            return [
                date_.strftime("%Y-%m-%d"),
                location.name,
                location.country,
                location.level_1,
                location.level_2,
                location.level_3,
                location.level_4,
                error_msg
            ]

        error_msg = _('Incorrect or no PMT data submitted')
        dates = rrule(
            DAILY,
            dtstart=self.startdate,
            until=self.enddate,
            byweekday=(MO, TU, WE, TH, FR, SA)
        )
        rows = []
        for date_ in dates:
            for location in get_locations(self.domain, self.report_config):
                pmt_submitted = location.id in self.pmts_submitted_by_date[date_.date()]
                if not pmt_submitted:
                    rows.append(_to_report_format(date_, location, error_msg))
        return rows


def iter_forms_by_xmlns_received_on(
    domain: str,
    xmlns: str,
    start_datetime: datetime,
    end_datetime: datetime,
) -> Iterator[XFormInstance]:
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
        & Q(state=XFormInstance.NORMAL)
        & Q(xmlns=xmlns)
        & Q(received_on__gte=start_datetime, received_on__lt=end_datetime)
    )
    return paginate_query_across_partitioned_databases(
        XFormInstance, q_expr, load_source='forms_by_xmlns_received_on'
    )


def midnight_starting(
    date_: date
) -> datetime:
    """
    Returns the start of the day

    >>> jan_1 = date(2000, 1, 1)
    >>> new_year = midnight_starting(jan_1)
    >>> new_year.isoformat()
    '2000-01-01T00:00:00'

    """
    return datetime(date_.year, date_.month, date_.day)


def midnight_ending(
    date_: date
) -> datetime:
    """
    Returns the end of the day

    >>> dec_31 = date(1999, 12, 31)
    >>> party_like_its = midnight_ending(dec_31)
    >>> party_like_its.isoformat()
    '2000-01-01T00:00:00'

    """
    return midnight_starting(date_ + timedelta(days=1))
