from __future__ import absolute_import
from django.utils.translation import ugettext_noop as _

WEEKLY_SUMMARY_XMLNS = 'http://openrosa.org/formdesigner/7EFB54F1-337B-42A7-9C6A-460AE8B0CDD8'

HF_MONTHLY_REPORT = [
    {
        'section': _('mc_section_home_visits'),
        'total_column': _('home_visits_total'),
        'columns': [
            _('home_visits_pregnant'),
            _('home_visits_postpartem'),
            _('home_visits_newborn'),
            _('home_visits_children'),
            _('home_visits_other'),
        ]
    },

    {
        'section': _('mc_section_rdt'),
        'total_column': _('rdt_total'),
        'columns': [
            _('rdt_positive_children'),
            _('rdt_positive_adults'),
            _('rdt_others'),
        ]
    },

    {
        'section': _('mc_section_diagnosed_cases'),
        'total_column': _('diagnosed_total'),
        'columns': [
            _('diagnosed_malaria_child'),
            _('diagnosed_malaria_adult'),
            _('diagnosed_diarrhea'),
            _('diagnosed_ari'),
        ]
    },

    {
        'section': _('mc_section_treated_cases'),
        'total_column': _('treated_total'),
        'columns': [
            _('treated_malaria'),
            _('treated_diarrhea'),
            _('treated_ari'),
        ]
    },

    {
        'section': _('mc_section_transfers'),
        'total_column': _('transfer_total'),
        'columns': [
            _('transfer_malnutrition'),
            _('transfer_incomplete_vaccination'),
            _('transfer_danger_signs'),
            _('transfer_prenatal_consult'),
            _('transfer_missing_malaria_meds'),
            _('transfer_other'),
        ]
    },

    {
        'section': _('mc_section_deaths'),
        'total_column': _('deaths_total'),
        'columns': [
            _('deaths_newborn'),
            _('deaths_children'),
            _('deaths_mothers'),
            _('deaths_other'),
        ]
    },
    {
        'section': _('mc_section_health_ed'),
        'columns': [
            _('heath_ed_talks'),
            _('heath_ed_participants'),
        ]
    },
]


DISTRICT_MONTHLY_REPORT = HF_MONTHLY_REPORT + [
    {
        'section': _('mc_section_stock_balance'),
        'type': 'form_lookup',
        'xmlns': WEEKLY_SUMMARY_XMLNS,
        'columns': [
            _('stock_amox_pink'),
            _('stock_amox_green'),
            _('stock_ors'),
            _('stock_ra_50'),
            _('stock_ra_200'),
            _('stock_zinc'),
            _('stock_coartem_yellow'),
            _('stock_coartem_blue'),
            _('stock_coartem_green'),
            _('stock_coartem_brown'),
            _('stock_paracetamol_250'),
            _('stock_paracetamol_500'),
            _('stock_rdt'),
            _('stock_gloves'),
        ]
    },
]

DISTRICT_WEEKLY_REPORT = [
    {
        'section': _('mc_section_home_visits'),
        'total_column': _('home_visits_total'),
        'columns': [
            _('home_visits_newborn'),
            _('home_visits_children'),
            _('home_visits_pregnant'),
            _('home_visits_non_pregnant'),
            _('home_visits_followup'),
        ]
    },
    {
        'section': _('mc_section_deaths_in_community'),
        'columns': [
            _('deaths_children'),
        ]
    },
    {
        'section': _('mc_section_stock_balance'),
        'type': 'form_lookup',
        'xmlns': WEEKLY_SUMMARY_XMLNS,
        'columns': [
            _('stock_coartem_yellow'),
            _('stock_coartem_blue'),
        ]
    },
    {
        'section': _('mc_section_validation'),
        'columns': [
            _('patients_given_pneumonia_meds'),
            _('patients_given_diarrhoea_meds'),
            _('patients_given_malaria_meds'),
            _('patients_correctly_referred'),
            _('cases_rdt_not_done'),
            _('cases_danger_signs_not_referred'),
            _('cases_no_malaria_meds'),
        ]
    },

]

HF_WEEKLY_REPORT = [
    {
        'section': _('mc_section_home_visits'),
        'total_column': _('home_visits_total'),
        'columns': [
            _('home_visits_newborn'),
            _('home_visits_children'),
            _('home_visits_adult'),
        ]
    },
    {
        'section': _('mc_section_transfers'),
        'columns': [
            _('cases_transferred'),
            _('home_visits_followup'),
            _('patients_given_pneumonia_meds'),
            _('patients_given_diarrhoea_meds'),
            _('patients_given_malaria_meds'),
            _('patients_correctly_referred'),
            _('cases_rdt_not_done'),
        ]
    },

]

# for now this is just a lookup for translations
HF_WEEKLY_MESSAGES = {
    'msg_children': _('Congratulations! This APE has visited {number} children this week. Call and congratulate them! Please help other supervisors learn from your success.'),
    'msg_pneumonia': _('This APE has treated {number} of patients with the incorrect medicine for pneumonia.  Please contact him/her and find out why and provide supportive supervision on use of amoxicillin.'),
    'msg_diarrhoea': _('This APE has treated {number} of patients with the incorrect medicine for diarrhoea.  Please contact them and find out why and provide supportive supervision on use of zinc and ORS.'),
    'msg_malaria': _('This APE has treated {number} of patients with the incorrect medicine for malaria.  Please contact them and find out why and provide supportive supervision on use of Coartem and Paracetamol.'),
    'msg_good_referrals': _('Congratulations! This APE has correctly referred all children they visited this week. Call those APEs to congratulate them! Please help other supervisors learn from your success.'),
    'msg_bad_referrals': _('This APE incorrectly referred {number} patients they visited this week. Please contact them and find out why and provide supportive supervision on correct referral.'),
    'msg_rdt': _('This APE did not perform a RDT on {number} patients with fever this week. Please contact them and find out why and provide supportive supervision on when to perform a RDT.'),
}
