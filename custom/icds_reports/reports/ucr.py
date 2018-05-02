from sqlalchemy.sql import func


class MPR2APersonCases(object):
    def __init__(self, report_data_source):
        self.report_data_source = report_data_source
        self.helper = self.report_data_source.helper

    @property
    def table(self):
        return self.helper.get_table()

    def _columns(self, total_row=False):
        table = self.table
        columns = (
            func.count(table.c.doc_id).filter(
                (table.c.closed_on != None) &
                (table.c.sex == "F") &
                (table.c.resident == "yes") &
                (table.c.date_death != None) &
                (table.c.dob != None) &
                ((table.c.date_death - table.c.dob).between(0, 28))
            ).label("dead_F_resident_neo_count"),
        )

        if not total_row:
            columns = (table.c.owner_id.label("owner_id"),) + columns

        return columns

    def _get_query_object(self, report_data_source, total_row=False):
        filters = self.helper.sql_alchemy_filters
        filter_values = self.helper.sql_alchemy_filter_values
        query = (
            self.helper.adapter.session_helper.Session.query(
                *self._columns(total_row)
            )
            .filter(*filters)
            .params(filter_values)
        )
        if not total_row:
            query = query.group_by(self.table.c.owner_id)
        return query

    def get_data(self, report_data_source, start, limit):
        query_obj = self._get_query_object(report_data_source)
        return [r._asdict() for r in query_obj.group_by(self.table.c.owner_id).all()]

    def get_total_row(self, report_data_source):
        query_obj = self._get_query_object(report_data_source, total_row=True)
        return ["Total"] + [r for r in query_obj.first()]

    def get_total_records(self, report_data_source):
        return self._get_query_object(report_data_source).count()

mpr_2a_person_cases = MPR2APersonCases
