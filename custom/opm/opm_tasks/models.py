from couchdbkit.ext.django.schema import (Document, StringProperty,
    StringListProperty, IntegerProperty, ListProperty)

from ..opm_reports.constants import DOMAIN


class OpmReportSnapshot(Document):
    """
    Represents a snapshot of a report, to be taken at the end of each month
    """
    domain = StringProperty()
    month = IntegerProperty()
    year = IntegerProperty()
    report_class = StringProperty()
    headers = StringListProperty()
    slugs = StringListProperty()
    rows = ListProperty()

    @classmethod
    def by_month(cls, month, year, report_class):
        return cls.view(
            'opm_tasks/opm_snapshots',
            key=[DOMAIN, month, year, report_class],
            reduce=False,
            include_docs=True
        ).first()
