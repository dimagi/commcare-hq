from __future__ import unicode_literals
def get_new_born_with_low_weight_help_text(html=False):
    return "Of all the children born and weighed in the current month and enrolled for Anganwadi services, " \
           "the percentage that had a birth weight less than 2500 grams. {}" \
           "Newborns with Low Birth Weight are closely associated with fetal and neonatal mortality and " \
           "morbidity, inhibited growth and cognitive development, and chronic diseases later in life. ".format(
               "<br/><br/>" if html else ""
           )
