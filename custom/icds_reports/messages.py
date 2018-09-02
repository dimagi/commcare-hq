from __future__ import unicode_literals, absolute_import
from django.utils.translation import ugettext as _


def wasting_help_text(age_label):
    return _(
        "Of the children enrolled for Anganwadi services, whose weight and height was measured, the "
        "percentage of children between {} enrolled who were moderately/severely wasted in the current month. "
        "<br/><br/>"
        "Severe Acute Malnutrition (SAM) or wasting in children is a symptom of acute undernutrition usually "
        "as a consequence of insufficient food intake or a high incidence of "
        "infectious diseases.".format(age_label)
    )


def stunting_help_text(age_label):
    return _(
        "Of the children whose height was measured, the percentage of children between {} who "
        "were moderately/severely stunted in the current month."
        "<br/><br/>"
        "Stunting is a sign of chronic undernutrition and has long lasting harmful "
        "consequences on the growth of a child".format(age_label)
    )
