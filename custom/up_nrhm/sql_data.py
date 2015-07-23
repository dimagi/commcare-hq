from sqlagg.base import CustomQueryColumn, QueryMeta, AliasColumn
from sqlagg.columns import CountUniqueColumn, SumWhen, SimpleColumn
from sqlagg.filters import BETWEEN, EQ, LTE
import sqlalchemy
from corehq.apps.reports.sqlreport import SqlData, DatabaseColumn, AggregateColumn
from corehq.apps.userreports.models import CustomDataSourceConfiguration
from corehq.apps.userreports.sql import get_table_name, get_indicator_table

TABLE_ID = 'asha_facilitators'
DOMAIN = 'up-nrhm'


class FunctionalityChecklistMeta(QueryMeta):
    """
    Custom query meta for ASHA Facilitators report. The report requires
    that each case be counted only once in the reporting period and that for
    each indicator only the most recent value be used.

    To accomplish this we need first query to find the most recent value for each
    case and then join the result with the original table to get the indicators.

    Produces SQL like this:

        select
            sum(case when hv_fx_vhnd = 1 then 1 else 0 end) as hv_fx_vhnd,
            sum(case when hv_fx_dots = 1 then 1 else 0 end) as hv_fx_dots
        from asha_facilitators as orig,
            (
                select
                    max(date), case_id
                from
                    asha_facilitators
                where
                    date between '2015-01-01' and '2015-02-01'
                    and owner_id = 'abcd'
                group by case_id
            ) as max
        where
            orig.case_id = max.case_id
            and orig.date = max.date
    """
    def __init__(self, table_name, filters, group_by):
        super(FunctionalityChecklistMeta, self).__init__(table_name, filters, group_by)
        self.columns = []

    def append_column(self, column):
        self.columns.append(column.sql_column)

    def get_asha_table(self, metadata):
        config = CustomDataSourceConfiguration.by_id(
            CustomDataSourceConfiguration.get_doc_id(DOMAIN, TABLE_ID)
        )
        return get_indicator_table(config, custom_metadata=metadata)

    def execute(self, metadata, connection, filter_values):
        asha_table = self.get_asha_table(metadata)

        max_date_query = sqlalchemy.select([
            sqlalchemy.func.max(asha_table.c.date).label('date'),
            asha_table.c.case_id.label('case_id')
        ])

        if self.filters:
            for filter in self.filters:
                max_date_query.append_whereclause(filter.build_expression())

        max_date_query.append_group_by(
            asha_table.c.case_id
        )

        max_date_subquery = sqlalchemy.alias(max_date_query, 'max_date')

        checklist_query = sqlalchemy.select()
        for column in self.columns:
            checklist_query.append_column(column.build_column(asha_table))

        checklist_query = checklist_query.where(
            asha_table.c.case_id == max_date_subquery.c.case_id
        ).where(
            asha_table.c.date == max_date_subquery.c.date
        )

        return connection.execute(checklist_query, **filter_values).fetchall()


class FunctionalityChecklistColumn(CustomQueryColumn):
    """
    Custom column that wraps SumWhen column types.

    This class is needed so link the FunctionalityChecklistMeta with the FunctionalityChecklistColumns
    """
    query_cls = FunctionalityChecklistMeta
    name = "functionality_checklist"

    def __init__(self, key=None, whens=None, *args, **kwargs):
        self.whens = whens
        super(FunctionalityChecklistColumn, self).__init__(key, *args, **kwargs)

    @property
    def sql_column(self):
        return SumWhen(self.key, whens=self.whens, else_=0, alias=self.alias).sql_column

    @property
    def column_key(self):
        """
        Override this to exclude the key so that all the columns get added to the same
        query meta instance (otherwise we'll be doing one query per column)
        """
        return self.name, self.table_name, str(self.filters), str(self.group_by)


class ASHAFacilitatorsData(SqlData):
    """
    Required config values:
    :startdate: start of date range
    :enddate:   end of date range
    :af:        User ID
    :domain:    domain name
    """
    slug = TABLE_ID

    @property
    def table_name(self):
        return get_table_name(self.config['domain'], self.slug)

    def _qualify_column(self, column):
        return '"{}".{}'.format(self.table_name, column)

    @property
    def columns(self):
        return [
            DatabaseColumn(
                "Total number of ASHAs under the Facilitator",
                CountUniqueColumn(
                    "case_id",
                    filters=[EQ('owner_id', 'af'), LTE('registration_date', 'enddate')],
                    alias="total_ashas"
                )
            ),
            DatabaseColumn(
                "Total number of ASHAs for whom functionality checklist was filled",
                FunctionalityChecklistColumn(
                    whens={'{} IS NOT NULL'.format(self._qualify_column('case_id')): 1},
                    alias="total_ashas_checklist"
                )
            ),
            DatabaseColumn(
                "Newborn visits within first day of birth in case of home deliveries",
                FunctionalityChecklistColumn('hv_fx_home_birth_visits', whens={1: 1}),
            ),
            DatabaseColumn(
                "Set of home visits for newborn care as specified in the HBNC guidelines<br/>"
                "(six visits in case of Institutional delivery and seven in case of a home delivery)",
                FunctionalityChecklistColumn('hv_fx_newborns_visited', whens={1: 1}),
            ),
            DatabaseColumn(
                "Attending VHNDs/Promoting immunization",
                FunctionalityChecklistColumn('hv_fx_vhnd', whens={1: 1}),
            ),
            DatabaseColumn(
                "Supporting institutional delivery",
                FunctionalityChecklistColumn('hv_fx_support_inst_delivery', whens={1: 1}),
            ),
            DatabaseColumn(
                "Management of childhood illness - especially diarrhea and pneumonia",
                FunctionalityChecklistColumn('hv_fx_child_illness_mgmt', whens={1: 1}),
            ),
            DatabaseColumn(
                "Household visits with nutrition counseling",
                FunctionalityChecklistColumn('hv_fx_nut_counseling', whens={1: 1}),
            ),
            DatabaseColumn(
                "Fever cases seen/malaria slides made in malaria endemic area",
                FunctionalityChecklistColumn('hv_fx_malaria', whens={1: 1}),
            ),
            DatabaseColumn(
                "Acting as DOTS provider",
                FunctionalityChecklistColumn('hv_fx_dots', whens={1: 1}),
            ),
            DatabaseColumn(
                "Holding or attending village/VHSNC meeting",
                FunctionalityChecklistColumn('hv_fx_vhsnc', whens={1: 1}),
            ),
            DatabaseColumn(
                "Successful referral of the IUD, "
                "female sterilization or male sterilization cases and/or providing OCPs/Condoms",
                FunctionalityChecklistColumn('hv_fx_fp', whens={1: 1}),
            ),
            AggregateColumn(
                "<b>Total number of ASHAs who are functional on at least 60% of the tasks</b>",
                aggregate_fn=lambda x, y: {
                    'sort_key': ((x or 0) * 100 / (y or 1)),
                    'html': '{0}/{1} ({2}%)'.format((x or 0), y, ((x or 0) * 100 / (y or 1)))
                },
                columns=[
                    FunctionalityChecklistColumn(
                        whens={'hv_percent_functionality >= 60': 1},
                        alias='percent_functionality'),
                    AliasColumn('total_ashas')
                ],
                format_fn=lambda x: x
            ),
        ]

    @property
    def filters(self):
        return [BETWEEN("date", "startdate", "enddate"), EQ('owner_id', 'af')]

    @property
    def group_by(self):
        return []


class ASHAFunctionalityChecklistData(SqlData):
    slug = 'asha_functionality_checklist'

    @property
    def table_name(self):
        return get_table_name(self.config['domain'], TABLE_ID)

    @property
    def columns(self):
        return [
            DatabaseColumn("Total number of ASHAs under the Facilitator", SimpleColumn("doc_id",)),
            DatabaseColumn("ASHA name", SimpleColumn("hv_asha_name",)),
            DatabaseColumn("Date of last for submission", SimpleColumn("completed_on",)),
        ]

    @property
    def filters(self):
        return [BETWEEN("date", "startdate", "enddate"), EQ('owner_id', 'af')]

    @property
    def group_by(self):
        return ['doc_id', 'date', 'hv_asha_name']


class ASHAAFChecklistData(SqlData):
    slug = 'asha_af_checklist'

    @property
    def table_name(self):
        return get_table_name(self.config['domain'], TABLE_ID)

    @property
    def columns(self):
        def convert_value(value):
            value_map = {1: 'Functional', 0: 'Not Functional', 88: 'Not Applicable'}
            return value_map.get(value)

        def percent(value):
            return "%d%%" % value

        return [
            DatabaseColumn("Date", SimpleColumn('completed_on')),
            DatabaseColumn("Newborn visits within first day of birth in case of home deliveries",
                           SimpleColumn("hv_fx_home_birth_visits"), format_fn=convert_value),
            DatabaseColumn("Set of home visits for newborn care as specified in the HBNC guidelines "
                           "(six visits in case of Institutional delivery and seven in case of a home delivery)",
                           SimpleColumn("hv_fx_newborns_visited",), format_fn=convert_value),
            DatabaseColumn("Attending VHNDs/Promoting immunization",
                           SimpleColumn("hv_fx_vhnd",), format_fn=convert_value),
            DatabaseColumn("Supporting institutional delivery",
                           SimpleColumn("hv_fx_support_inst_delivery",), format_fn=convert_value),
            DatabaseColumn("Management of childhood illness - especially diarrhea and pneumonia",
                           SimpleColumn("hv_fx_child_illness_mgmt",), format_fn=convert_value),
            DatabaseColumn("Household visits with nutrition counseling",
                           SimpleColumn("hv_fx_nut_counseling",), format_fn=convert_value),
            DatabaseColumn("Fever cases seen/malaria slides made in malaria endemic area",
                           SimpleColumn("hv_fx_malaria",), format_fn=convert_value),
            DatabaseColumn("Acting as DOTS provider",
                           SimpleColumn("hv_fx_dots",), format_fn=convert_value),
            DatabaseColumn("Holding or attending village/VHSNC meeting",
                           SimpleColumn("hv_fx_vhsnc",), format_fn=convert_value),
            DatabaseColumn("Successful referral of the IUD, female sterilization or male sterilization cases "
                           "and/or providing OCPs/Condoms",
                           SimpleColumn("hv_fx_fp",), format_fn=convert_value),
            DatabaseColumn("Functionality Score", SimpleColumn("hv_percent_functionality",), format_fn=percent)
        ]

    @property
    def filters(self):
        return [EQ('doc_id', 'doc_id')]

    @property
    def group_by(self):
        return []

    @property
    def rows(self):
        return [[index + 1, column.header, column.get_value(self.data)]
                for index, column in enumerate(self.columns)]
