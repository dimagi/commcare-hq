from sqlagg.columns import CountUniqueColumn
from sqlagg.filters import BETWEEN, EQ, GTE, LTE
from sqlagg.queries.alchemy_extensions import InsertFromSelect
import sqlalchemy
from corehq.apps.reports.sqlreport import SqlData, DatabaseColumn
from corehq.apps.userreports.models import CustomDataSourceConfiguration
from corehq.apps.userreports.sql import get_table_name, get_indicator_table
from corehq.db import Session


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
    """
    CREATE TEMPORARY TABLE asha AS
    select case_id, hv_fx_vhnd = 1 as hv_fx_vhnd from "config_report_up-nrhm_asha_facilitators_faeb40fd" rd,
    (
        select max(date) date, case_id as cid
        from "config_report_up-nrhm_asha_facilitators_faeb40fd"
        where date between '2015-01-01' and '2015-02-01'
        group by case_id
        ) as max

    where case_id = max.cid and rd.date = max.date and case_id = 'b77bc08a-6453-43b1-8d17-6d9d9e45feac'


    select case_id, count(case_id)
        from "config_report_up-nrhm_asha_facilitators_faeb40fd"
        where date between '2015-01-01' and '2015-02-01'
        group by case_id

    select *
    from "config_report_up-nrhm_asha_facilitators_faeb40fd"
    where case_id = 'b77bc08a-6453-43b1-8d17-6d9d9e45feac'

    "2015-01-03", hv_fx_vhnd = 0
    "2015-01-21", hv_fx_vhnd = 88


    select 1 FROM pg_catalog.pg_class c LEFT JOIN pg_catalog.pg_namespace n ON n.oid
    = c.relnamespace
    where n.nspname like 'pg_temp_%' AND pg_catalog.pg_table_is_visible(c.oid)
    AND Upper(relname) = Upper('asaha');

    """
    slug = 'asha_facilitators'
    title = 'ASHA Facilitators report'
    show_total = False

    @property
    def table_name(self):
        return get_table_name(self.config['domain'], 'asha_facilitators')

    def _get_temp_table_name(self):
        start_date = self.config["startdate"].strftime("%Y-%m-%d")
        end_date = self.config["enddate"].strftime("%Y-%m-%d")
        return "tmp_{name}_{start}_{end}".format(
            name=self.table_name,
            start=start_date,
            end=end_date
        )

    @property
    def columns(self):
        return [
            sqlalchemy.Column('hv_fx_vhnd', sqlalchemy.BOOLEAN)
        ]

    def get_sql_table(self, metadata):
        config = CustomDataSourceConfiguration.by_id(CustomDataSourceConfiguration.get_doc_id(self.slug))
        return get_indicator_table(config, custom_metadata=metadata)

    def data(self):
        session = Session()
        try:
            data = self._get_sql_data(session)
        except:
            session.rollback()
            raise

    def _get_sql_data(self, session):
        metadata = sqlalchemy.MetaData()
        metadata.bind = session.connection()

        # todo: check if temp table exists
        temp_table = sqlalchemy.Table(self._get_temp_table_name(), metadata,
                             sqlalchemy.Column("case_id", sqlalchemy.VARCHAR, primary_key=True),
                             prefixes=['TEMPORARY'])

        for column in self.columns:
            temp_table.append_column(column)

        asha_table = self.get_sql_table(metadata)
        max_date_query = sqlalchemy.select(
            sqlalchemy.func.max(asha_table.c.date).label('date'),
            asha_table.c.case_id.label('case_id')
        ).where(
            asha_table.date.between(':startdate', ':enddate')
        ).group_by(
            asha_table.c.case_id
        )

        temp_table_query = sqlalchemy.select(
            asha_table.c.case_id,
            (asha_table.c.hv_fx_vhnd == 1).label('hv_fx_vhnd')
        ).join(
            max_date_query,
            asha_table.c.case_id == max_date_query.c.case_id,
            asha_table.c.date == max_date_query.c.date,
        )

        # create temp table
        from_select = InsertFromSelect(temp_table, temp_table_query, self.columns)
        session.execute(from_select)