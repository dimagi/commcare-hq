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


def awcs_launched_help_text():
    return _(
        'Total AWCs that have launched ICDS-CAS. AWCs are considered launched after submitting at least '
        'one Household Registration form. '
    )


def percent_aadhaar_seeded_beneficiaries_help_text():
    return _(
        'Of the total number of ICDS beneficiaries, the percentage whose Adhaar '
        'identification has been captured. '
    )


def percent_children_enrolled_help_text(age_label="0-6 years"):
    return _(
        'Of the total number of children between {}, '
        'the percentage of children who are enrolled for Anganwadi Services'.format(age_label)
    )


def percent_pregnant_women_enrolled_help_text():
    return _(
        'Of the total number of pregnant women, '
        'the percentage of pregnant women enrolled for Anganwadi Services'
    )


def percent_lactating_women_enrolled_help_text():
    return _(
        'Of the total number of lactating women, '
        'the percentage of lactating women enrolled for Anganwadi Services'
    )


def percent_adolescent_girls_enrolled_help_text():
    return _(
        "Of the total number of adolescent girls (aged 11-14 years), "
        "the percentage of girls enrolled for Anganwadi Services"
    )


def awcs_reported_clean_drinking_water_help_text():
    return _(
        'Of the AWCs that have submitted an Infrastructure Details form, the '
        'percentage of AWCs that reported having a source of clean drinking water. '
    )


def awcs_reported_functional_toilet_help_text():
    return _(
        'Of the AWCs that submitted an Infrastructure Details form, the percentage '
        'of AWCs that reported having a functional toilet'
    )


def awcs_reported_weighing_scale_infants_help_text():
    return _(
        'Of the AWCs that have submitted an Infrastructure Details form, the '
        'percentage of AWCs that reported having a weighing scale for infants'
    )


def awcs_reported_weighing_scale_mother_and_child_help_text():
    return _(
        'Of the AWCs that have submitted an Infrastructure Details form, the percentage of '
        'AWCs that reported having a weighing scale for mother and child'
    )


def awcs_reported_medicine_kit_help_text():
    return _(
        'Of the AWCs that have submitted an Infrastructure Details form, '
        'the percentage of AWCs that reported having a Medicine Kit'
    )


def lady_supervisor_number_of_awcs_visited_help_text():
    return _(
        'Number of AWCs visited: Number of AWC visit forms submitted by LS in current month'
    )


def lady_supervisor_number_of_beneficiaries_visited_help_text():
    return _(
        'Number of Beneficiaries visited: Number of beneficiaries visited by LS in the current month'
    )


def lady_supervisor_number_of_vhnds_observed_help_text():
    return _(
        'Number of VHSND observed: Number of VHSND observed by LS in the current month'
    )
