from __future__ import unicode_literals
from django.utils.translation import ugettext as _


def wasting_help_text(beta):
    if beta:
        return _(
            "Percentage of children between 0-5 years enrolled for Anganwadi Services with "
            "weight-for-height below -2 standard deviations of the WHO Child Growth Standards median. "
            "<br/><br/>"
            "Severe Acute Malnutrition (SAM) or wasting in children is a symptom of acute "
            "undernutrition usually as a consequence of insufficient food intake or a high "
            "incidence of infectious diseases."
        )
    return _(
        "Percentage of children (6-60 months) with weight-for-height below -3 standard "
        "deviations of the WHO Child Growth Standards median."
        "<br/><br/>"
        "Severe Acute Malnutrition (SAM) or wasting in children is a symptom of acute "
        "undernutrition usually as a consequence of insufficient food intake or a high "
        "incidence of infectious diseases."
    )


def stunting_help_text(beta):
    if beta:
        return _(
            "Percentage of children between 0-5 years enrolled for Anganwadi Services  with "
            "height-for-age below -2Z standard deviations of the WHO Child Growth Standards median. "
            "<br/><br/>"
            "Stunting is a sign of chronic undernutrition and has long lasting harmful consequences "
            "on the growth of a child"
        )
    return _(
        "Percentage of children (6-60 months) with height-for-age below -2Z standard deviations "
        "of the WHO Child Growth Standards median."
        "<br/><br/>"
        "Stunting is a sign of chronic undernutrition "
        "and has long lasting harmful consequences on the growth of a child"
    )
