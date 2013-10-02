from django.utils.translation import ugettext_noop as _

from custom.apps.crs_reports.reports import HBNCMotherReport, HBNCInfantReport


CUSTOM_REPORTS = (
    (_('Custom Reports'), (
       HBNCMotherReport,
       HBNCInfantReport,
    )),
)

EXTEND_URL_PATTERN = True

QUESTION_TEMPLATES = (
    (HBNCMotherReport.slug, [
        {'case_property': '',
        'question': _('In case of death, was information of death given to MOI/c by ASHA within 24 hours or not'),
        },
        {'case_property': 'bleeding',
        'question': _('Bleeding/watery discharge: How many times does she change pad in a day.'),
        },
        {'case_property': '',
        'question': _('If mother said more than 5 pads were wet and referral made, what was outcome of referral?'),
        },
        {'case_property': 'meals',
        'question': _('How many times mother is taking full meals?'),
        },
        {'case_property': 'meals_counsel',
        'question': _('If mother is taking food less than 4 times or not taking complete diet, did ASHA counsel her to do so?'),
        },
        {'case_property': 'mother_temp',
        'question': _('Measurements of Fever (degrees C or F)'),
        },
        {'case_property': '',
        'question': _('Outcome of referrals to the hospital for fever.'),
        },
        {'case_property': 'discharge',
        'question': _('Does the mother have foul smeling discharge or pus along with fever above 102 degrees F (38.9 degrees Celsius)?'),
        },
        {'case_property': 'maternal_fits',
        'question': _('Sub consciousness/fits/speaking abnormally'),
        },
        {'case_property': '',
        'question': _('Any other serious problems?'),
        }
    ]),
    (HBNCInfantReport.slug, [])
)