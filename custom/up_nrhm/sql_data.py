from sqlagg.columns import CountColumn
from sqlagg.filters import BETWEEN, EQ, GTE
from corehq.apps.reports.sqlreport import SqlData, DatabaseColumn


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
                CountColumn(
                    "doc_id",
                    alias="all_functional"
                )
            ),
            DatabaseColumn(
                "Newborn visits within first day of birth in case of home deliveries",
                CountColumn(
                    "doc_id",
                    filters=self.filters + [EQ("home_birth_last_month_visited_total", "count_one")],
                    alias="home_birth_count"
                )
            ),
            DatabaseColumn(
                "Set of home visits for newborn care as specified in the HBNC guidelines"
                "(six visits in case of Institutional delivery and seven in case of a home delivery)",
                CountColumn(
                    "doc_id",
                    filters=self.filters + [EQ("hv_fx_newborns_visited_total", "count_one")],
                    alias="newborns_count"
                )
            ),
            DatabaseColumn(
                "Attending VHNDs/Promoting immunization",
                CountColumn(
                    "doc_id",
                    filters=self.filters + [EQ("hv_fx_vhnd_total", "count_one")],
                    alias="vhnd_count"
                )
            ),
            DatabaseColumn(
                "Supporting institutional delivery",
                CountColumn(
                    "doc_id",
                    filters=self.filters + [EQ("hv_fx_support_inst_delivery_total", "count_one")],
                    alias="delivery_count"
                )
            ),
            DatabaseColumn(
                "Management of childhood illness - especially diarrhea and pneumonia",
                CountColumn(
                    "doc_id",
                    filters=self.filters + [EQ("hv_fx_child_illness_mgmt_total", "count_one")],
                    alias="mgmt_count"
                )
            ),
            DatabaseColumn(
                "Household visits with nutrition counseling",
                CountColumn(
                    "doc_id",
                    filters=self.filters + [EQ("hv_fx_nut_counseling_total", "count_one")],
                    alias="counseling_count"
                )
            ),
            DatabaseColumn(
                "Fever cases seen/malaria slides made in malaria endemic area",
                CountColumn(
                    "doc_id",
                    filters=self.filters + [EQ("hv_fx_malaria_total", "count_one")],
                    alias="malaria_count"
                )
            ),
            DatabaseColumn(
                "Acting as DOTS provider",
                CountColumn(
                    "doc_id",
                    filters=self.filters + [EQ("hv_fx_dots_total", "count_one")],
                    alias="dots_count"
                )
            ),
            DatabaseColumn(
                "Holding or attending village/VHSNC meeting",
                CountColumn(
                    "doc_id",
                    filters=self.filters + [EQ("hv_fx_vhnd_total", "count_one")],
                    alias="fx_vhnd_count"
                )
            ),
            DatabaseColumn(
                "Successful referral of the IUD, "
                "female sterilization or male sterilization cases and/or providing OCPs/Condoms",
                CountColumn(
                    "doc_id",
                    filters=self.filters + [EQ("hv_fx_fp_total", "count_one")],
                    alias="fx_count"
                )
            ),
            DatabaseColumn(
                "Total number of ASHAs who are functional on at least 6/10 tasks",
                CountColumn(
                    "hv_percent_functionality_total",
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
