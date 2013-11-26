from django.utils.translation import ugettext_noop as _
from custom.reports.mc.models import WEEKLY_SUMMARY_XMLNS

HF_MONTHLY_REPORT = [
    {
        'section': _('Home Visits'),
        'columns': [
            _('home_visits_pregnant'),
            _('home_visits_postpartem'),
            _('home_visits_newborn'),
            _('home_visits_children'),
            _('home_visits_other'),
            _('home_visits_total'),
        ]
    },

    {
        'section': _('RDT'),
        'columns': [
            _('rdt_positive_children'),
            _('rdt_positive_adults'),
            _('rdt_others'),
            _('rdt_total'),
        ]
    },

    {
        'section': _('Diagnosed Cases'),
        'columns': [
            _('diagnosed_malaria_child'),
            _('diagnosed_malaria_adult'),
            _('diagnosed_diarrhea'),
            _('diagnosed_ari'),
            _('diagnosed_total'),
        ]
    },

    {
        'section': _('Treated Cases'),
        'columns': [
            _('treated_malaria'),
            _('treated_diarrhea'),
            _('treated_ari'),
            _('treated_total'),
        ]
    },

    {
        'section': _('Transfers'),
        'columns': [
            _('transfer_malnutrition'),
            _('transfer_incomplete_vaccination'),
            _('transfer_danger_signs'),
            _('transfer_prenatal_consult'),
            _('transfer_missing_malaria_meds'),
            _('transfer_other'),
            _('transfer_total'),
        ]
    },

    {
        'section': _('Deaths'),
        'columns': [
            _('deaths_newborn'),
            _('deaths_children'),
            _('deaths_mothers'),
            _('deaths_other'),
            _('deaths_total'),
        ]
    },
    {
        'section': _('Health Education'),
        'columns': [
            _('heath_ed_talks'),
            _('heath_ed_participants'),
        ]
    },
]

# todo: need to add additional columns for district report
DISTRICT_MONTHLY_REPORT = HF_MONTHLY_REPORT + [
    {
        'section': _('Stock Balance'),
        'type': 'form_lookup',
        'xmlns': WEEKLY_SUMMARY_XMLNS,
        'columns': [
            _('form/stock/stock_amox_pink'),
            _('form/stock/stock_amox_green'),
            _('form/stock/stock_ors'),
            _('form/stock/stock_ra_50'),
            _('form/stock/stock_ra_200'),
            _('form/stock/stock_zinc'),
            _('form/stock/stock_coartem_yellow'),
            _('form/stock/stock_coartem_blue'),
            _('form/stock/stock_coartem_green'),
            _('form/stock/stock_coartem_brown'),
            _('form/stock/stock_paracetamol_250'),
            _('form/stock/stock_paracetamol_500'),
            _('form/stock/stock_rdt'),
            _('form/stock/stock_gloves'),
        ]
    },
]

DISTRICT_WEEKLY_REPORT = [
    {
        'section': _('Home Visits'),
        'columns': [
            _('home_visits_newborn'),
            _('home_visits_children'),
            _('home_visits_pregnant'),
            _('home_visits_non_pregnant'),
            _('home_visits_followup'),
            _('home_visits_total'),
        ]
    },
    {
        'section': _('Deaths in the Community'),
        'columns': [
            _('deaths_children'),
        ]
    },
    {
        'section': _('Stock Balance'),
        'type': 'form_lookup',
        'xmlns': WEEKLY_SUMMARY_XMLNS,
        'columns': [
            _('form/stock/stock_coartem_yellow'),
            _('form/stock/stock_coartem_blue'),
        ]
    },
    {
        'section': _('Validation of Diagnosis and Treatment'),
        'columns': [
            {
                'slug': _('patients_given_pneumonia_meds'),
                'columns': ('patients_given_pneumonia_meds_num', 'patients_given_pneumonia_meds_denom'),
            },
            {
                'slug': _('patients_given_diarrhoea_meds'),
                'columns': ('patients_given_diarrhoea_meds_num', 'patients_given_diarrhoea_meds_denom'),
            },
            {
                'slug': _('patients_given_malaria_meds'),
                'columns': ('patients_given_malaria_meds_num', 'patients_given_malaria_meds_denom'),
            },
            {
                'slug': _('patients_correctly_referred'),
                'columns': ('patients_correctly_referred_num', 'patients_correctly_referred_denom'),
            },
            _('cases_rdt_not_done'),
            _('cases_danger_signs_not_referred'),
            _('cases_no_malaria_meds'),
        ]
    },

]

HF_WEEKLY_REPORT = [
    {
        'section': _('Home Visits'),
        'columns': [
            _('home_visits_newborn'),
            _('home_visits_children'),
            _('home_visits_adult'),
            _('home_visits_total'),
        ]
    },
    {
        'section': _('Transferred Cases'),
        'columns': [
            _('cases_transferred'),
            _('home_visits_followup'),
            {
                'slug': _('patients_given_pneumonia_meds'),
                'columns': ('patients_given_pneumonia_meds_num', 'patients_given_pneumonia_meds_denom'),
            },
            {
                'slug': _('patients_given_diarrhoea_meds'),
                'columns': ('patients_given_diarrhoea_meds_num', 'patients_given_diarrhoea_meds_denom'),
            },
            {
                'slug': _('patients_given_malaria_meds'),
                'columns': ('patients_given_malaria_meds_num', 'patients_given_malaria_meds_denom'),
            },
            {
                'slug': _('patients_correctly_referred'),
                'columns': ('patients_correctly_referred_num', 'patients_correctly_referred_denom'),
            },
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
