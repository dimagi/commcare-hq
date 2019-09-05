# coding=utf-8

from custom.intrahealth.reports.consommation_dashboard import ConsommationReport
from custom.intrahealth.reports.dashboard_1 import Dashboard1Report
from custom.intrahealth.reports.disponibilite_dashboard import DisponibiliteReport
from custom.intrahealth.reports.dashboard_2 import Dashboard2Report
from custom.intrahealth.reports.dashboard_3 import Dashboard3Report
from custom.intrahealth.reports.fiche_consommation_report import FicheConsommationReport
from custom.intrahealth.reports.indicateurs_de_base_dasboard import IndicateursDeBaseReport
from custom.intrahealth.reports.recap_passage_one_dashboard import RecapPassageOneReport
from custom.intrahealth.reports.recap_passage_report import RecapPassageReport
from custom.intrahealth.reports.recap_passage_two_dashboard import RecapPassageTwoReport
from custom.intrahealth.reports.tableu_de_board_report import TableuDeBoardReport
from custom.intrahealth.reports.tableu_de_board_report_v2 import TableuDeBoardReport2
from custom.intrahealth.reports.fiche_consommation_report_v2 import FicheConsommationReport2
from custom.intrahealth.reports.recap_passage_report_v2 import RecapPassageReport2
from custom.intrahealth.reports.taux_de_peremption_dashboard import TauxDePeremptionReport
from custom.intrahealth.reports.taux_de_perte_dashboard import TauxDePerteReport
from custom.intrahealth.reports.taux_de_rupture_dashboard import TauxDeRuptureReport
from custom.intrahealth.reports.taux_de_satisfaction_dashboard import TauxDeSatisfactionReport
from custom.intrahealth.reports.valuer_des_stocks_pna_disponible_dashboard import ValuerDesStocksPNADisponsibleReport

CUSTOM_REPORTS = (
    ('INFORMED PUSH MODEL REPORTS', (
        TableuDeBoardReport,
        FicheConsommationReport,
        RecapPassageReport
    )),
    ('ANCIENS RAPPORTS YEKSI NAA', (
        Dashboard1Report,
        Dashboard2Report,
        Dashboard3Report,
    )),
    ('NOUVEAUX RAPPORTS YEKSI NAA', (
        DisponibiliteReport,
        TauxDeRuptureReport,
        ConsommationReport,
        TauxDePerteReport,
        TauxDePeremptionReport,
        TauxDeSatisfactionReport,
        ValuerDesStocksPNADisponsibleReport,
        RecapPassageOneReport,
        RecapPassageTwoReport,
        IndicateursDeBaseReport,
    )),
    ("INFORMED PUSH MODEL REPORTS UCR", (
        TableuDeBoardReport2,
        FicheConsommationReport2,
        RecapPassageReport2,
    ))
)
