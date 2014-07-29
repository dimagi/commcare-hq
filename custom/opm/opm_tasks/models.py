from couchdbkit.ext.django.schema import (Document, StringProperty,
    StringListProperty, IntegerProperty, ListProperty)

from ..opm_reports.constants import DOMAIN, InvalidRow


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
    block = StringProperty()
    visible_cols = ListProperty()

    @classmethod
    def by_month(cls, month, year, report_class, block=None):
        return cls.view(
            'opm_tasks/opm_snapshots',
            key=[DOMAIN, month, year, report_class, block],
            reduce=False,
            include_docs=True
        ).first()

    @classmethod
    def filtered(cls, snapshot, report):
        filtered_rows = []

        need_filering = False
        filters = []
        keys_list = []
        for key, field in report.filter_fields:
            keys = report.filter_data.get(field, [])
            if keys:
                need_filering = True
                filters.append((key, field))
                if field == 'gp':
                    keys_list.append([user._id for user in report.users if 'user_data' in user and 'gp' in user.user_data and
                        user.user_data['gp'] and user.user_data['gp'] in keys])
                else:
                    keys_list.append(keys)
        if need_filering:

            def get_slug(key):
                if key in snapshot.slugs:
                    return snapshot.slugs.index(key)
                return None

            filters = filter(lambda x: x is not None, [get_slug(key) for key, value in filters])
            get_element = lambda row, i: row[i] if row[i] else ""
            for row in snapshot.rows:
                values = [(bool(keys_list[i]) and get_element(row, f) in keys_list[i]) for i, f in enumerate(filters)]
                if all(values):
                    filtered_rows.append(row)
            snapshot.rows = filtered_rows
        return snapshot

    @classmethod
    def from_view(cls, report):
        block = None
        if report.block:
            block = report.block.lower()
        snapshot = cls.view(
            'opm_tasks/opm_snapshots',
            key=[DOMAIN, report.month, report.year, report.__class__.__name__, block],
            reduce=False,
            include_docs=True
        ).first()
        if not snapshot:
            return None
        return cls.filtered(snapshot, report)
