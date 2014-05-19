from django.utils.translation import ugettext_noop as _

from custom.apps.crs_reports.reports import HBNCMotherReport

MOTHER_POSTPARTUM_VISIT_FORM_XMLNS = "http://openrosa.org/formdesigner/63866D7C-42FC-43DD-8EFA-E02C74729DD6"
BABY_POSTPARTUM_VISIT_FORM_XMLNS = "http://openrosa.org/formdesigner/EA8FB6FC-E269-440F-993E-AD07F733BF31"

CUSTOM_REPORTS = (
    (_('Custom Reports'), (
       HBNCMotherReport,
    )),
)

QUESTION_TEMPLATES = (
    (HBNCMotherReport.slug, [
        { 'questions' :[
            {'case_property': 'section_a',
             'question': _('A. Ask Mother.')
            },
            {'case_property': 'meals',
            'question': _('Number of times mother takes full meals in 24 hours?'),
            },
            {'case_property': 'bleeding',
            'question': _('Bleeding. How many Pads are changed in a day?'),
            },
            {'case_property': 'warm',
            'question': _('During the cold season is the baby being kept warm?'),
            },
            {'case_property': 'feeding',
            'question': _('Is the baby being fed properly?'),
            },
            {'case_property': 'incessant_cry',
            'question': _('Is the baby crying incessantly or passing urine less than 6 times?'),
            },
            {'case_property': 'section_b',
            'question': _('B. Examination of mother'),
            },
            {'case_property': 'maternal_temp',
            'question': _('Temperature: Measure and Record?'),
            },
            {'case_property': 'discharge',
            'question': _('Foul Smelling Discharge?'),
            },
            {'case_property': 'maternal_fits',
            'question': _('Is mother speaking normally or having fits'),
            },
            {'case_property': 'no_milk',
            'question': _('Mother has no milk since delivery or less milk'),
            },
            {'case_property': 'sore_breast',
            'question': _('Cracked Nipples/Painful or Engorged Breast/'),
            }]
        },
        { 'questions' :[
            {'case_property': 'section_c',
             'question': _('C.  Examination of Baby')
            },
            {'case_property': 'baby_eye',
            'question': _('Eyes Swollen with pus?'),
            },
            {'case_property': 'weight',
            'question': _('Weight (7,14,21,28)?'),
            },
            {'case_property': 'baby_temp',
            'question': _('Temperature: Measure and Record?'),
            },
            {'case_property': 'pustules',
            'question': _('Skin: Pus filled pustules?'),
            },
            {'case_property': 'cracks',
            'question': _('Cracks and Redness on the skin fold?'),
            },
            {'case_property': 'jaundice',
            'question': _('Yellowness in eyes'),
            }]
        },
        { 'questions' :[
            {'case_property': 'section_d',
             'question': _('D.  Sepsis Signs Checkup')
            },
            {'case_property': 'limbs',
            'question': _('All limbs up?'),
            },
            {'case_property': 'feeding_less',
            'question': _('Feeding Less/Stopped?'),
            },
            {'case_property': 'cry',
            'question': _('Cry Weak/Stopped?'),
            },
            {'case_property': 'abdomen_vomit',
            'question': _('Distant Abdomen?'),
            },
            {'case_property': 'cold',
            'question': _('Baby Cold to touch?'),
            },
            {'case_property': 'chest',
            'question': _('Chest Indrawing?'),
            },
            {'case_property': 'pus',
            'question': _('Pus on umbilicus?'),
            }]
        }
    ]),
)