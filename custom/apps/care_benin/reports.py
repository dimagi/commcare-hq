# coding=utf-8

from numbers import Number
from corehq.apps.reports.basic import BasicTabularReport, Column, GenericTabularReport
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumnGroup, \
    DataTablesColumn, DTSortType
from corehq.apps.reports.standard import ProjectReportParametersMixin, CustomProjectReport, DatespanMixin
from corehq.apps.reports.filters.dates import DatespanFilter
from corehq.apps.groups.models import Group
from couchdbkit_aggregate import KeyView, AggregateKeyView, fn
from dimagi.utils.couch.loosechange import map_reduce
from dimagi.utils.decorators.memoized import memoized
from couchdbkit_aggregate.fn import NO_VALUE
from dimagi.utils.couch.database import get_db
from corehq.apps.reports.util import format_datatables_data as fdd
from corehq.apps.reports import util

RELAIS_GROUP = "relais"

AGENTS_DE_SANTE_GROUP = "Agents de Santé"


def username(key, report):
    return report.usernames[key[0]]


def groupname(key, report):
    return report.groupnames[key[0]]


def combine_indicator(num, denom):
    if isinstance(num, Number) and isinstance(denom, Number):
        return '%s %% (%s / %s)' % (num * 100 / denom, num, denom)
    else:
        return NO_VALUE


class CareGroupReport(BasicTabularReport, CustomProjectReport, ProjectReportParametersMixin, DatespanMixin):
    field_classes = (DatespanFilter,)
    datespan_default_days = 30
    exportable = True

    @property
    def start_and_end_keys(self):
        return ([self.datespan.startdate_param_utc],
                [self.datespan.enddate_param_utc])

    @property
    def keys(self):
        for group in self.groups:
            yield [group._id]

    @property
    def groups(self):
        return [g for g in Group.by_domain(self.domain) if not g.reporting]

    @property
    @memoized
    def groupnames(self):
        return dict([(group._id, group.name) for group in self.groups])


def td_format(millis):
    td_seconds = millis / 1000
    periods = [
        ('day', 60*60*24),
        ('hour', 60*60),
        ('minute', 60),
    ]

    for name, seconds in periods:
        if td_seconds > seconds:
            value, seconds = divmod(td_seconds, seconds)
            if value == 1:
                return "%s %s" % (value, name)
            else:
                return "%s %ss" % (value, name)


class MeanTime(fn.mean):

    def __call__(self, stats):
        millis = super(MeanTime, self).__call__(stats, 0)
        if isinstance(millis, Number):
            return td_format(millis)
        else:
            return millis


class MandE(CareGroupReport):
    name = "M&E"
    slug = "cb_m_and_e"

    couch_view = "care_benin/by_village_case"

    default_column_order = (
        'village',

        'referrals_open_30_days',
        'ref_counter_ref_time',
        'danger_sign_knowledge_pregnancy',
        'danger_sign_knowledge_post_partum',
        'danger_sign_knowledge_newborn',
        'birth_place_mat_isolee',
        'birth_place_centre_de_sante',
        'birth_place_cs_arrondissement',
        'birth_place_cs_commune',
        'birth_place_hopital',
        'birth_place_domicile',
        'birth_place_clinique_privee',
        'birth_place_autre',

        'newlyRegisteredPregnant',
        'postPartumRegistration',
        'pregnant_followed_up',
        #'high_risk_pregnancy', #requires village in form
        #'anemic_pregnancy', #requires village in form
        #'stillborns', #requires village in form
        #'failed_pregnancy', #requires village in form
        #'maternal_death', #requires village in form
        #'child_death_7_days', #requires village in form
        'births_one_month_ago_bcg_polio',
        'births_vat2',
        'births_tpi2',
        'births_one_month_ago_follow_up_x0',
        'births_one_month_ago_follow_up_x1',
        'births_one_month_ago_follow_up_x2',
        'births_one_month_ago_follow_up_x3',
        'births_one_month_ago_follow_up_x4',
        'births_one_month_ago_follow_up_gt4',
        #'danger_sign_count_pregnancy', #requires village in form
        #'danger_sign_count_newborn', #requires village in form
        'births_cpn0',
        'births_cpn1',
        'births_cpn2',
        'births_cpn4',
    )

    village = Column(
        "Village", calculate_fn=groupname)

    ref_counter_ref_time = Column("Mean time between reference and counter reference", key="ref_counter_ref_time",
                                  reduce_fn=MeanTime(),
                                  help_text="Délai entre la référence et la contre référence des agents de santé")

    # birth
    birth_place_help = "Distribution des lieux d’accouchement par village"
    birth_place_group = DataTablesColumnGroup("Birth place")
    birth_place_mat_isolee = Column("Maternite Isolee", key="birth_place_mat_isolee",
                                    group=birth_place_group,
                                    help_text=birth_place_help)
    birth_place_centre_de_sante = Column("centre de santé", key="birth_place_centre_de_sante",
                                    group=birth_place_group,
                                    help_text=birth_place_help)
    birth_place_cs_arrondissement = Column("CS Arrondissement", key="birth_place_CS_arrondissement",
                                           group=birth_place_group,
                                           help_text=birth_place_help)
    birth_place_cs_commune = Column("CS Commune", key="birth_place_CS_commune",
                                    group=birth_place_group,
                                    help_text=birth_place_help)
    birth_place_hopital = Column("Hopital de zone", key="birth_place_hopital",
                                 group=birth_place_group,
                                 help_text=birth_place_help)
    birth_place_domicile = Column("Domicile", key="birth_place_domicile",
                                  group=birth_place_group,
                                  help_text=birth_place_help)
    birth_place_clinique_privee = Column("Clinique Privee", key="birth_place_clinique_privee",
                                         group=birth_place_group,
                                         help_text=birth_place_help)
    birth_place_autre = Column("Autre lieu", key="birth_place_autre",
                               group=birth_place_group,
                               help_text=birth_place_help)

    referrals_open_30_days = Column("Referrals open for more than one month", key="referrals_open_30_days",
                                    startkey_fn=lambda x: [],
                                    help_text="Nombre de cas de référence ouverts pendant plus d’un mois")

    #danger signs
    danger_sign_knowledge_group = DataTablesColumnGroup("Danger sign knowledge")
    danger_sign_knowledge_pregnancy = Column("Pregnancy danger sign knowledge",
                                             key="danger_sign_knowledge_pregnancy",
                                             startkey_fn=lambda x: [], group=danger_sign_knowledge_group,
                                             help_text="""Nombre de femmes qui connaissent au moins 3 signes
                                             de danger de la femme enceinte par village""")
    danger_sign_knowledge_post_partum = Column("Post-partum danger sign knowledge",
                                               key="danger_sign_knowledge_post_partum",
                                               startkey_fn=lambda x: [], group=danger_sign_knowledge_group,
                                               help_text="""Nombre de femmes qui connaissent au moins 3 signes
                                               de danger de la nouvelle accouchée par village""")
    danger_sign_knowledge_newborn = Column("Newborn danger sign knowledge",
                                           key="danger_sign_knowledge_newborn",
                                           startkey_fn=lambda x: [], group=danger_sign_knowledge_group,
                                           help_text="""Nombre de femmes qui connaissent au moins 3
                                           signes de danger du nouveau-né par village""")

    # pregnancy
    newlyRegisteredPregnant = Column("Newly Registered Women who are Pregnant",
                                     key="newly_registered_pregnant",
                                     help_text="""Nombre de cas de femmes enceintes
                                     enregistrées et ouverts par village""")

    pregnant_followed_up = Column("Pregnant women followed up on", key="pregnant_followed_up",
                                  startkey_fn=lambda x: [], endkey_fn=lambda x: [{}],
                                  help_text="Nombre de femmes enceintes suivies par village")

    high_risk_pregnancy = Column("High risk pregnancies", key="high_risk_pregnancy",
                                 couch_view="care_benin/by_village_form", startkey_fn=lambda x: [],
                                 help_text="Nombre de grossesse à risque détectés par village")

    anemic_pregnancy = Column("Anemic pregnancies", key="anemic_pregnancy",
                              couch_view="care_benin/by_village_form", startkey_fn=lambda x: [],
                              help_text="Nombre de femmes enceintes souffrant d’anémie par village")

    # birth
    postPartumRegistration = Column(
        "Post-partum mothers/newborn registrations", key="post_partum_registration",
        help_text="Nombre de cas de nouvelles accouchées enregistrées et ouverts par village")

    stillborns = Column("Stillborns", key="stillborn",
                        couch_view="care_benin/by_village_form", startkey_fn=lambda x: [],
                        help_text="Nombre de mort-nés par village   Seulement pour les accouchements chez le CS")

    failed_pregnancy = Column("Failed pregnancies", key="pregnancy_failed",
                              couch_view="care_benin/by_village_form", startkey_fn=lambda x: [],
                              help_text="""Nombre de fausses couches par village Est-ce que ça inclue
                        les grossesse échoués? – tout grosseses arreter avant 6m""")

    maternal_death = Column("Maternal deaths", key="maternal_death",
                            couch_view="care_benin/by_village_form", startkey_fn=lambda x: [],
                            help_text="Nombre de décès maternels par village")

    child_death_7_days = Column("Babies died before 7 days", key="child_death_7_days",
                                couch_view="care_benin/by_village_form", startkey_fn=lambda x: [],
                                help_text="Nombre de décès d’enfants de moins de 7 jours par village ")

    births_total_view = KeyView(key="birth_one_month_ago")

    births_view_x0 = AggregateKeyView(combine_indicator,
                                      KeyView(key="birth_one_month_ago_followup_x0"),
                                      births_total_view)
    births_view_x1 = AggregateKeyView(combine_indicator,
                                      KeyView(key="birth_one_month_ago_followup_x1"),
                                      births_total_view)
    births_view_x2 = AggregateKeyView(combine_indicator,
                                      KeyView(key="birth_one_month_ago_followup_x2"),
                                      births_total_view)
    births_view_x3 = AggregateKeyView(combine_indicator,
                                      KeyView(key="birth_one_month_ago_followup_x3"),
                                      births_total_view)
    births_view_x4 = AggregateKeyView(combine_indicator,
                                      KeyView(key="birth_one_month_ago_followup_x4"),
                                      births_total_view)
    births_view_gt4 = AggregateKeyView(combine_indicator,
                                       KeyView(key="birth_one_month_ago_followup_gt4"),
                                       births_total_view)

    births_one_month_ago_follow_up_help = """Distribution des accouchées/nouveau-nés par nombre de visites
     de suivi pour les accouchements ayant eu lieu le mois précédent par village"""
    births_one_month_ago_follow_up_group = DataTablesColumnGroup("Birth followup percentages")
    births_one_month_ago_follow_up_x0 = Column(
        "Birth followups X0", key=births_view_x0, group=births_one_month_ago_follow_up_group,
        help_text=births_one_month_ago_follow_up_help)
    births_one_month_ago_follow_up_x1 = Column(
        "Birth followups X1", key=births_view_x1, group=births_one_month_ago_follow_up_group,
        help_text=births_one_month_ago_follow_up_help)
    births_one_month_ago_follow_up_x2 = Column(
        "Birth followups X2", key=births_view_x2, group=births_one_month_ago_follow_up_group,
        help_text=births_one_month_ago_follow_up_help)
    births_one_month_ago_follow_up_x3 = Column(
        "Birth followups X3", key=births_view_x3, group=births_one_month_ago_follow_up_group,
        help_text=births_one_month_ago_follow_up_help)
    births_one_month_ago_follow_up_x4 = Column(
        "Birth followups X4", key=births_view_x4, group=births_one_month_ago_follow_up_group,
        help_text=births_one_month_ago_follow_up_help)
    births_one_month_ago_follow_up_gt4 = Column(
        "Birth followups >4", key=births_view_gt4, group=births_one_month_ago_follow_up_group,
        help_text=births_one_month_ago_follow_up_help)

    birth_cpn_total = KeyView(key="birth_cpn_total")

    births_cpn0_view = AggregateKeyView(combine_indicator,
                                        KeyView(key='birth_cpn_0'),
                                        birth_cpn_total)
    births_cpn1_view = AggregateKeyView(combine_indicator,
                                        KeyView(key='birth_cpn_1'),
                                        birth_cpn_total)
    births_cpn2_view = AggregateKeyView(combine_indicator,
                                        KeyView(key='birth_cpn_2'),
                                        birth_cpn_total)
    births_cpn4_view = AggregateKeyView(combine_indicator,
                                        KeyView(key='birth_cpn_4'),
                                        birth_cpn_total)

    # TODO: no help text
    birth_cpn_group = DataTablesColumnGroup("Birth with CPN")
    births_cpn0 = Column("Birth with CPN0", key=births_cpn0_view, group=birth_cpn_group)
    births_cpn1 = Column("Birth with CPN1", key=births_cpn1_view, group=birth_cpn_group)
    births_cpn2 = Column("Birth with CPN2", key=births_cpn2_view, group=birth_cpn_group)
    births_cpn4 = Column("Birth with CPN4", key=births_cpn4_view, group=birth_cpn_group)

    births_vat2 = Column("Birth with VAT2", key="birth_vat_2", help_text="""Nombre de femmes enceintes
        ayant reçu 2 VAT avant l’accouchement par village""")
    births_tpi2 = Column("Birth with TPI2", key="birth_tpi_2", help_text="""Nombre de femmes enceintes
        ayant reçu la 2ème dose de TPI/SP avant l’accouchement par village""")

    births_one_month_ago_bcg_polio = Column("Births 2 months ago that got BCG polio",
                                            key='birth_one_month_ago_bcg_polio',
                                            help_text="""Nombre de nouveau-né ayant reçu la vaccination
                                            BCG/Polio pour les nouveau-nés nés le mois précédent par village""")

    #danger signs
    danger_sign_count_group = DataTablesColumnGroup("Danger sign counts")
    danger_sign_count_pregnancy = Column("Pregnancy danger sign count", key="danger_sign_count_pregnancy",
                                         group=danger_sign_count_group,
                                         help_text="""Nombre de cas de femmes enceintes/accouchées/nouveau-nés
                                         ayant eu de(s) signe(s) de danger par village""")
    danger_sign_count_newborn = Column("Newborn danger sign count", key="danger_sign_count_birth",
                                       group=danger_sign_count_group,
                                       help_text="""Nombre de cas de femmes enceintes/accouchées/nouveau-nés
                                       ayant eu de(s) signe(s) de danger par village""")


class Relais(BasicTabularReport, CustomProjectReport, ProjectReportParametersMixin, DatespanMixin):
    name = "Relais"
    slug = "cb_relais"
    field_classes = (DatespanFilter,)
    datespan_default_days = 30
    exportable = True
    filter_group_name = RELAIS_GROUP

    couch_view = "care_benin/by_village_case"

    default_column_order = (
        'relais',
        'ref_suiviref_time',
    )

    relais = Column("Relais", calculate_fn=username)

    ref_suiviref_time = Column("Mean time between referral and suivi de referral",
                               key="ref_suiviref_time", reduce_fn=MeanTime(),
                               help_text="Délai entre la référence et le suivi de la référence")

    @property
    def start_and_end_keys(self):
        return ([self.datespan.startdate_param_utc],
                [self.datespan.enddate_param_utc])

    @property
    def keys(self):
        for user in self.users:
            yield [user['user_id']]


class Nurse(BasicTabularReport, CustomProjectReport, ProjectReportParametersMixin, DatespanMixin):
    name = "Nurse"
    slug = "cb_nurse"
    field_classes = (DatespanFilter,)
    datespan_default_days = 30
    exportable = True
    filter_group_name = AGENTS_DE_SANTE_GROUP

    couch_view = "care_benin/by_user_form"

    default_column_order = (
        'nurse',
        'cpn_exam_rate',
        'post_natal_followups_15m', #requires xform_xmlns in case actions
        'post_natal_followups_6h', #requires xform_xmlns in case actions
        'post_natal_followups_sortie', #requires xform_xmlns in case actions
        'post_natal_followups_none', #requires xform_xmlns in case actions
    )

    nurse = Column("Nurse", calculate_fn=username)

    cpn_exam_total = KeyView(key="cpn_exam_total")

    cpn_exam_rate_view = AggregateKeyView(combine_indicator,
                                          KeyView(key="cpn_exam_answered"),
                                          cpn_exam_total)

    cpn_exam_rate = Column("CPN Exam Rate", key=cpn_exam_rate_view,
                           help_text="""Proportion de protocoles d’examen
                           CPN entièrement respecté (rempli) par agent de santé""")

    post_natal_followups_total_view = KeyView(key="post_natal_followups_total",
                                              couch_view="care_benin/by_village_case", startkey_fn=lambda x: [])
    post_natal_followups_15m_view = AggregateKeyView(combine_indicator,
                                                     KeyView(key="post_natal_followups_15m",
                                                             couch_view="care_benin/by_village_case", startkey_fn=lambda x: []),
                                                     post_natal_followups_total_view)
    post_natal_followups_6h_view = AggregateKeyView(combine_indicator,
                                                    KeyView(key="post_natal_followups_6h",
                                                            couch_view="care_benin/by_village_case", startkey_fn=lambda x: []),
                                                    post_natal_followups_total_view)
    post_natal_followups_sortie_view = AggregateKeyView(combine_indicator,
                                                        KeyView(key="post_natal_followups_sortie",
                                                                couch_view="care_benin/by_village_case", startkey_fn=lambda x: []),
                                                        post_natal_followups_total_view)
    post_natal_followups_none_view = AggregateKeyView(combine_indicator,
                                                      KeyView(key="post_natal_followups_none",
                                                              couch_view="care_benin/by_village_case", startkey_fn=lambda x: []),
                                                      post_natal_followups_total_view)

    pnf_help="""Proportion d’accouchés suivi à 15 min  Proportion d’accouchés suivi à 6h,
        Proportion d’accouchés suivi avant la sortie Par agent de santé"""
    pnf_group = DataTablesColumnGroup("Post-natal followups")
    post_natal_followups_15m = Column("15 min follow up", key=post_natal_followups_15m_view,
                                      group=pnf_group, help_text=pnf_help)
    post_natal_followups_6h = Column("6 hour follow up", key=post_natal_followups_6h_view,
                                     group=pnf_group, help_text=pnf_help)
    post_natal_followups_sortie = Column("Sortie follow up", key=post_natal_followups_sortie_view,
                                         group=pnf_group, help_text=pnf_help)
    post_natal_followups_none = Column("No follow up", key=post_natal_followups_none_view,
                                       group=pnf_group, help_text=pnf_help)

    @property
    def start_and_end_keys(self):
        return ([self.datespan.startdate_param_utc],
                [self.datespan.enddate_param_utc])

    @property
    def keys(self):
        for user in self.users:
            yield [user['user_id']]


class Referrals(CareGroupReport):
    name = "Referrals"
    slug = "cb_referrals"

    couch_view = "care_benin/by_village_form"

    # NOTE: all require village to be loaded into the forms
    default_column_order = (
        'village',
        'references_to_clinic',
        'referrals_transport_pied',
        'referrals_transport_velo',
        'referrals_transport_barque_simple',
        'referrals_transport_barque_ambulance',
        'referrals_transport_vehicule_simple',
        'referrals_transport_vehicule_ambulance',
        'referrals_transport_moto_simple',
        'referrals_transport_moto_ambulance',
        'referrals_by_type_enceinte',
        'referrals_by_type_accouchee',
        'referrals_by_type_nouveau_ne',
    )

    village = Column("", calculate_fn=lambda key, report: '')#groupname)

    referrals_total_view = KeyView(key="referrals_transport_total")

    referrals_transport_pied_view = AggregateKeyView(combine_indicator,
                                                     KeyView(key="referrals_transport_pied"),
                                                     referrals_total_view)
    referrals_transport_velo_view = AggregateKeyView(combine_indicator,
                                                     KeyView(key="referrals_transport_velo"),
                                                     referrals_total_view)
    referrals_transport_barque_simple_view = AggregateKeyView(combine_indicator,
                                                              KeyView(key="referrals_transport_barque_simple"),
                                                              referrals_total_view)
    referrals_transport_barque_ambulance_view = AggregateKeyView(combine_indicator,
                                                                 KeyView(key="referrals_transport_barque_ambulance"),
                                                                 referrals_total_view)
    referrals_transport_vehicule_simple_view = AggregateKeyView(combine_indicator,
                                                                KeyView(key="referrals_transport_vehicule_simple"),
                                                                referrals_total_view)
    referrals_transport_vehicule_ambulance_view = AggregateKeyView(combine_indicator,
                                                                   KeyView(
                                                                       key="referrals_transport_vehicule_ambulance"),
                                                                   referrals_total_view)
    referrals_transport_moto_simple_view = AggregateKeyView(combine_indicator,
                                                            KeyView(key="referrals_transport_moto_simple"),
                                                            referrals_total_view)
    referrals_transport_moto_ambulance_view = AggregateKeyView(combine_indicator,
                                                               KeyView(key="referrals_transport_moto_ambulance"),
                                                               referrals_total_view)

    rt_help = "Distribution des moyens de transport des cas référés par village"
    referrals_transport_group = DataTablesColumnGroup("Referrals by mode of transport")
    referrals_transport_pied = Column("Pied", key=referrals_transport_pied_view,
                                      group=referrals_transport_group, help_text=rt_help)
    referrals_transport_velo = Column("Velo", key=referrals_transport_velo_view,
                                      group=referrals_transport_group, help_text=rt_help)
    referrals_transport_barque_simple = Column("Barque simple", key=referrals_transport_barque_simple_view,
                                               group=referrals_transport_group, help_text=rt_help)
    referrals_transport_barque_ambulance = Column("Barque ambulance", key=referrals_transport_barque_ambulance_view,
                                                  group=referrals_transport_group, help_text=rt_help)
    referrals_transport_vehicule_simple = Column("Vehicule simple", key=referrals_transport_vehicule_simple_view,
                                                 group=referrals_transport_group, help_text=rt_help)
    referrals_transport_vehicule_ambulance = Column("Vehicule ambulance",
                                                    key=referrals_transport_vehicule_ambulance_view,
                                                    group=referrals_transport_group, help_text=rt_help)
    referrals_transport_moto_simple = Column("Moto simple", key=referrals_transport_moto_simple_view,
                                             group=referrals_transport_group, help_text=rt_help)
    referrals_transport_moto_ambulance = Column("Moto ambulance", key=referrals_transport_moto_ambulance_view,
                                                group=referrals_transport_group, help_text=rt_help)

    rtype_help = "Nombre de référence de enc/acc/nne par village"
    referrals_type_group = DataTablesColumnGroup("Referrals by patient type")
    referrals_by_type_enceinte = Column("Enceinte", key="referral_per_type_enceinte",
                                        group=referrals_type_group, help_text=rtype_help)
    referrals_by_type_accouchee = Column("Accouchee", key="referral_per_type_accouchee",
                                         group=referrals_type_group, help_text=rtype_help)
    referrals_by_type_nouveau_ne = Column("Nouveau Ne", key="referral_per_type_nouveau_ne",
                                          group=referrals_type_group, help_text=rtype_help)

    references_to_clinic_view = AggregateKeyView(combine_indicator,
                                                 KeyView(key="reference_to_clinic_went"),
                                                 KeyView(key="reference_to_clinic"))
    references_to_clinic = Column("Rate of references which went to clinic",
                                  key=references_to_clinic_view, help_text="Taux de références fermées qui sont "
                                                                           "allées au centre de santé par village")

    @property
    def keys(self):
        return [['village']]


class Outcomes(GenericTabularReport, CustomProjectReport, ProjectReportParametersMixin, DatespanMixin):
    name = "Outcomes"
    slug = "cb_outcomes"
    fields = ('corehq.apps.reports.filters.dates.DatespanFilter',)
    datespan_default_days = 30
    exportable = True

    couch_view = "care_benin/outcomes"

    row_list = (
        {
            "name": "Cases opened (enceinte)",
            "view": KeyView(key="case_opened_enceinte")
        },
        {
            "name": "Cases opened (accouchee)",
            "view": KeyView(key="case_opened_accouchee")
        },
        {
            "name": "Cases closed (enceinte)",
            "view": KeyView(key="case_closed_enceinte")
        },
        {
            "name": "Cases closed (accouchee)",
            "view": KeyView(key="case_closed_accouchee")
        },
        {
            "name": "Percentage of births at clinic",
            "view": AggregateKeyView(combine_indicator, KeyView(key="births_at_clinic"), KeyView(key="births_total"))
        },
        {
            "name": "Percentage of births at clinic with GATPA performed",
            "view": AggregateKeyView(combine_indicator, KeyView(key="birth_gapta"), KeyView(key="birth_total_gapta"))
        },
        {
            "name": "Birth with VAT2",
            "view": KeyView("birth_vat_2")
        },
        {
            "name": "Birth with TPI2",
            "view": KeyView("birth_tpi_2")
        },
        {
            "name": "Failed pregnancies",
            "view": KeyView(key="pregnancy_failed")
        },
        {
            "name": "Maternal deaths",
            "view": KeyView(key="maternal_death")
        },
        {
            "name": "Babies died before 7 days",
            "view": KeyView(key="child_death_7_days")
        },
        {
            "name": "Total references to clinic (enceinte)",
            "view": KeyView(key="references_to_clinic_total_enceinte")
        },
        {
            "name": "Total references to clinic (accouchee)",
            "view": KeyView(key="references_to_clinic_total_accouchee")
        },
    )

    @property
    def start_and_end_keys(self):
        self.datespan.inclusive = False
        return ([self.datespan.startdate_param],
                [self.datespan.enddate_param])

    @property
    def headers(self):
        return DataTablesHeader(DataTablesColumn("", sortable=False),
                                DataTablesColumn("Value", sort_type=DTSortType.NUMERIC))

    @property
    def rows(self):
        db = get_db()
        startkey, endkey = self.start_and_end_keys
        for row in self.row_list:
            value = row["view"].get_value([], startkey=startkey, endkey=endkey, couch_view=self.couch_view, db=db)
            yield [row["name"], fdd(value, value)]


class DangerSigns(GenericTabularReport, CustomProjectReport, ProjectReportParametersMixin, DatespanMixin):
    name = "Danger sign distribution"
    slug = "cb_danger"
    fields = ('corehq.apps.reports.filters.dates.DatespanFilter',)
    datespan_default_days = 30
    exportable = True

    @property
    def start_and_end_keys(self):
        return (self.datespan.startdate_param_utc,
                self.datespan.enddate_param_utc)

    @property
    def keys(self):
        return [row['key'] for row in get_db().view("care_benin/danger_signs",
                                                       reduce=True, group=True,
                                                       group_level=2)]

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn("Danger sign"),
            DataTablesColumn("Count (enceinte)", sort_type=DTSortType.NUMERIC),
            DataTablesColumn("Count (accouchee)", sort_type=DTSortType.NUMERIC),
            DataTablesColumn("Count (nne)", sort_type=DTSortType.NUMERIC),
        )

    @property
    def rows(self):
        reduce_fn = fn.sum()
        startkey, endkey = self.start_and_end_keys

        row_dict = {}

        for key in self.keys:
            row = get_db().view("care_benin/danger_signs",
                                startkey=key + [startkey],
                                endkey=key + [endkey, {}],
                                reduce=True,
                                wrapper=lambda r: r['value']
            )

            row = row.first()
            val = reduce_fn(row)

            cols = row_dict.setdefault(
                key[1],
                {
                    'danger_sign_count_pregnancy': [],
                    'danger_sign_count_accouchee': [],
                    'danger_sign_count_birth': [],
                }
            )
            if val != NO_VALUE:
                cols[key[0]].append(val)

        for sign, cols in row_dict.items():
            pregnancy = sum(cols['danger_sign_count_pregnancy'])
            accouchee = sum(cols['danger_sign_count_accouchee'])
            birth = sum(cols['danger_sign_count_birth'])
            yield [
                sign,
                fdd(pregnancy, pregnancy),
                fdd(accouchee, accouchee),
                fdd(birth, birth)
            ]


def health_center_name(key, report):
    return report.hc[key[0]]


class HealthCenter(BasicTabularReport, CustomProjectReport, ProjectReportParametersMixin, DatespanMixin):
    name = "Health Center"
    slug = "health_center"
    field_classes = (DatespanFilter,)
    datespan_default_days = 30
    exportable = True
    filter_group_name = AGENTS_DE_SANTE_GROUP

    couch_view = "care_benin/by_user_form"

    default_column_order = (
        'health_center',
        'cpn_exam_forms',
        'new_acceptants_for_fp',
        'birth_complications_referred',
        'stillborns',
        'high_risk_pregnancy',
        'pregnant_anemia',
    )

    health_center = Column("Health Center", calculate_fn=health_center_name)

    cpn_exam_forms = Column("Women received for CPN", key='cpn_exam_forms')

    new_acceptants_for_fp = Column("Number of new acceptants for FP methods",
                                   key='acceptants_for_fp')

    birth_complications_referred = Column("# referred women for complications during birth",
                                          key='birth_complications_referred')

    stillborns = Column("Number of stillborns", key='stillborn')

    high_risk_pregnancy = Column("Number of high risk pregnancies detected", key='high_risk_pregnancy')

    pregnant_anemia = Column("Number of pregnant women with anemia", key='pregnant_anemia')

    @memoized
    def get_all_users_by_domain(self, group=None, user_ids=None, user_filter=None, simplified=False):
        return list(util.get_all_users_by_domain(
            domain=self.domain,
            group=group,
            user_ids=user_ids,
            user_filter=user_filter,
            simplified=False,  # override simplified to False
            CommCareUser=self.CommCareUser
        ))

    @property
    @memoized
    def hc(self):
        return dict([(user.get_id, user.user_data.get('CS')) for user in self.users])

    @property
    def start_and_end_keys(self):
        return ([self.datespan.startdate_param_utc],
                [self.datespan.enddate_param_utc])

    @property
    def keys(self):
        return [[user.get_id] for user in self.users]

    @property
    def rows(self):
        rows = list(super(HealthCenter, self).rows)
        rows_by_hc = map_reduce(emitfunc=lambda r: [(r[0],)], reducefunc=self.reduce, data=rows, include_docs=True)
        return rows_by_hc.values()

    def reduce(self, rows):
        if not rows:
            return rows

        def unwrap(row):
            return [val['sort_key'] if isinstance(val, dict) else val for val in row]

        def combine(vals):
            nums = [v for v in vals if isinstance(v, int)]
            if nums:
                res = sum(nums)
                return fdd(res, res)
            else:
                val = vals[0]
                if val is None:
                    val = NO_VALUE
                return fdd(val, val)

        return [combine(unwrap(x)) for x in zip(*rows)]

CUSTOM_REPORTS = (
    ('CARE Benin Special Reports', (
        MandE,
        Nurse,
        Relais,
        DangerSigns,
        Referrals,
        HealthCenter,
        Outcomes,
    )),
)
