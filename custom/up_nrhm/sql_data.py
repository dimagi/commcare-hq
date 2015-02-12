from sqlagg.base import CustomQueryColumn, QueryMeta
from sqlagg.columns import CountUniqueColumn, SumWhen
from sqlagg.filters import BETWEEN, EQ, GTE, LTE
import sqlalchemy
from corehq.apps.reports.sqlreport import SqlData, DatabaseColumn
from corehq.apps.userreports.models import CustomDataSourceConfiguration
from corehq.apps.userreports.sql import get_table_name, get_indicator_table

DOMAIN = 'up-nrhm'

TABLE_ID = 'asha_facilitators'


class FunctionalityChecklistMeta(QueryMeta):
    def __init__(self, table_name, filters, group_by):
        super(FunctionalityChecklistMeta, self).__init__(table_name, filters, group_by)
        self.columns = []

    def append_column(self, column):
        self.columns.append(column.sql_column)

    def get_asha_table(self, metadata):
        config = CustomDataSourceConfiguration.by_id(CustomDataSourceConfiguration.get_doc_id(TABLE_ID))
        return get_indicator_table(config, custom_metadata=metadata)

    def real_table_name(self):
        return get_table_name(DOMAIN, self.table_name)

    def execute(self, metadata, connection, filter_values):
        """
        select
            sum(case when hv_fx_vhnd = 1 then 1 else 0 end) as hv_fx_vhnd,
            sum(case when hv_fx_dots = 1 then 1 else 0 end) as hv_fx_dots
        from "config_report_up-nrhm_asha_facilitators_faeb40fd" rd,
            (
                select max(date) date, case_id as cid
                from "config_report_up-nrhm_asha_facilitators_faeb40fd"
                where date between '2015-01-01' and '2015-02-01'
                group by case_id
            ) as max
        where
            case_id = max.cid and rd.date = max.date
        """
        asha_table = self.get_asha_table(metadata)

        max_date_query = sqlalchemy.select([
            sqlalchemy.func.max(asha_table.c.date).label('date'),
            asha_table.c.case_id.label('case_id')
        ]).where(
            asha_table.c.date.between(filter_values['startdate'], filter_values['enddate'])
        ).group_by(
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
    query_cls = FunctionalityChecklistMeta
    name = "functionality_checklist"

    def __init__(self, key, whens, *args, **kwargs):
        self.whens = whens
        super(FunctionalityChecklistColumn, self).__init__(key, *args, **kwargs)

    @property
    def sql_column(self):
        return SumWhen(self.key, whens=self.whens, else_=0, alias=self.alias).sql_column

    @property
    def column_key(self):
        return self.name, self.table_name, str(self.filters), str(self.group_by)


class ASHAFacilitatorsData(SqlData):
    slug = 'asha_facilitators'
    title = 'ASHA Facilitators report'
    show_total = False
    table_name = 'fluff_ASHAFacilitatorsFluff'

    @property
    def columns(self):
        return [
            DatabaseColumn(
                "Total number of ASHAs under the Facilitator",
                CountUniqueColumn(
                    "case_id",
                    filters=[EQ('owner_id', 'af'), LTE('registration_date', 'enddate_str')],
                    alias="all_functional"
                )
            ),
            DatabaseColumn(
                "Total number of ASHAs for whom functionality checklist was filled",
                CountUniqueColumn(
                    "case_id",
                    alias="all_checklist_filled"
                )
            ),
            DatabaseColumn(
                "Newborn visits within first day of birth in case of home deliveries",
                CountUniqueColumn(
                    "case_id",
                    filters=self.filters + [EQ("home_birth_last_month_visited_total", "count_one")],
                    alias="home_birth_count"
                )
            ),
            DatabaseColumn(
                "Set of home visits for newborn care as specified in the HBNC guidelines"
                "(six visits in case of Institutional delivery and seven in case of a home delivery)",
                CountUniqueColumn(
                    "case_id",
                    filters=self.filters + [EQ("hv_fx_newborns_visited_total", "count_one")],
                    alias="newborns_count"
                )
            ),
            DatabaseColumn(
                "Attending VHNDs/Promoting immunization",
                CountUniqueColumn(
                    "case_id",
                    filters=self.filters + [EQ("hv_fx_vhnd_total", "count_one")],
                    alias="vhnd_count"
                )
            ),
            DatabaseColumn(
                "Supporting institutional delivery",
                CountUniqueColumn(
                    "case_id",
                    filters=self.filters + [EQ("hv_fx_support_inst_delivery_total", "count_one")],
                    alias="delivery_count"
                )
            ),
            DatabaseColumn(
                "Management of childhood illness - especially diarrhea and pneumonia",
                CountUniqueColumn(
                    "case_id",
                    filters=self.filters + [EQ("hv_fx_child_illness_mgmt_total", "count_one")],
                    alias="mgmt_count"
                )
            ),
            DatabaseColumn(
                "Household visits with nutrition counseling",
                CountUniqueColumn(
                    "case_id",
                    filters=self.filters + [EQ("hv_fx_nut_counseling_total", "count_one")],
                    alias="counseling_count"
                )
            ),
            DatabaseColumn(
                "Fever cases seen/malaria slides made in malaria endemic area",
                CountUniqueColumn(
                    "case_id",
                    filters=self.filters + [EQ("hv_fx_malaria_total", "count_one")],
                    alias="malaria_count"
                )
            ),
            DatabaseColumn(
                "Acting as DOTS provider",
                CountUniqueColumn(
                    "case_id",
                    filters=self.filters + [EQ("hv_fx_dots_total", "count_one")],
                    alias="dots_count"
                )
            ),
            DatabaseColumn(
                "Holding or attending village/VHSNC meeting",
                CountUniqueColumn(
                    "case_id",
                    filters=self.filters + [EQ("hv_fx_vhnd_total", "count_one")],
                    alias="fx_vhnd_count"
                )
            ),
            DatabaseColumn(
                "Successful referral of the IUD, "
                "female sterilization or male sterilization cases and/or providing OCPs/Condoms",
                CountUniqueColumn(
                    "case_id",
                    filters=self.filters + [EQ("hv_fx_fp_total", "count_one")],
                    alias="fx_count"
                )
            ),
            DatabaseColumn(
                "Total number of ASHAs who are functional on at least 6/10 tasks",
                CountUniqueColumn(
                    "case_id",
                    filters=self.filters + [GTE("hv_percent_functionality_total", "sixty_percents")],
                    alias="percent_functionality"
                )
            ),
        ]

    @property
    def group_by(self):
        return ["owner_id"]

    @property
    def filters(self):
        return [BETWEEN("date", "startdate", "enddate"), EQ('owner_id', 'af')]


class ASHAFacilitatorsDataNew(SqlData):
    slug = 'asha_facilitators'
    title = 'ASHA Facilitators report'
    show_total = False

    @property
    def table_name(self):
        return get_table_name(self.config['domain'], self.slug)

    @property
    def columns(self):
        return [
            DatabaseColumn(
                "Attending VHNDs/Promoting immunization",
                FunctionalityChecklistColumn('hv_fx_vhnd', whens={1: 1}),
            ),
            DatabaseColumn(
                "Acting as DOTS provider",
                FunctionalityChecklistColumn('hv_fx_dots', whens={1: 1}),
            ),
        ]

    @property
    def filters(self):
        return []

    @property
    def group_by(self):
        return []
