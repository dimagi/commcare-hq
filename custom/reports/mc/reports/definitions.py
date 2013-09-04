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
            _('home_visits_newborn_reg'),
            _('home_visits_child_reg'),
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
    # {
    #     'section': _('Stock Balance'),
    #     'columns': [
    #         'heath_ed_talks',
    #         'heath_ed_participants',
    #     ]
    # },
    {
        'section': _('Validation of Diagnosis and Treatment'),
        'columns': [
            # todo: display num/denom groupings
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


