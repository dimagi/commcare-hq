from __future__ import unicode_literals, absolute_import
from django.utils.translation import ugettext as _


def wasting_help_text(age_label):
    return _(
        "Of the children enrolled for Anganwadi services, whose weight and height was measured, the "
        "percentage of children between {} who were moderately/severely wasted in the current month. "
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


def new_born_with_low_weight_help_text(html=False):
    return _(
        "Of all the children born and weighed in the current month and enrolled for Anganwadi services, "
        "the percentage that had a birth weight less than 2500 grams. {}"
        "Newborns with Low Birth Weight are closely associated with fetal and neonatal mortality and "
        "morbidity, inhibited growth and cognitive development, and chronic diseases later in life. ".format(
            "<br/><br/>" if html else ""
        )
    )


def underweight_children_help_text(age_label="0-5 years", html=False):
    return _(
        "Of the total children enrolled for Anganwadi services and weighed, the percentage "
        "of children between {} who were moderately/severely underweight in the current "
        "month. {}Children who are moderately or severely underweight have a higher risk "
        "of mortality. ".format(age_label, "<br/><br/>" if html else "")
    )


def early_initiation_breastfeeding_help_text(html=False):
    return _(
        "Of the children born in the last month and enrolled for Anganwadi services, the percentage "
        "whose breastfeeding was initiated within 1 hour of delivery. {}"
        "Early initiation of breastfeeding ensure the newborn recieves the \"first milk\" rich in "
        "nutrients and encourages exclusive breastfeeding practice".format("<br/><br/>" if html else "")
    )


def exclusive_breastfeeding_help_text(html=False):
    return _(
        "Of the total children enrolled for Anganwadi services between the ages of 0 to 6 months, "
        "the percentage that was exclusively fed with breast milk. {}"
        "An infant is exclusively breastfed if they receive only breastmilk with no additional food or liquids "
        "(even water), ensuring optimal nutrition and growth between 0 - 6 months".format(
            "<br/><br/>" if html else ""
        )
    )


def children_initiated_appropriate_complementary_feeding_help_text(html=False):
    return _(
        "Of the total children enrolled for Anganwadi services between the ages of 6 to 8 months, the percentage "
        "that was given a timely introduction to solid, semi-solid or soft food. {}"
        "Timely intiation of complementary feeding in addition to breastmilk at 6 months of age is a key feeding "
        "practice to reduce malnutrition".format(
            "<br/><br/>" if html else ""
        )
    )


def institutional_deliveries_help_text(html=False):
    return _(
        "Of the total number of women enrolled for Anganwadi services who gave birth in the last month, the "
        "percentage who delivered in a public or private medical facility. {}"
        "Delivery in medical instituitions is associated with a decrease in maternal mortality rate".format(
            "<br/><br/>" if html else ""
        )
    )
