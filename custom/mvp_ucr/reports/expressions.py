from jsonobject import JsonObject
from corehq.apps.userreports.specs import TypeProperty

NEONATE_FORM = "http://openrosa.org/formdesigner/5cd541d5a1034f02c922dc888416148a89b85ffa"
CHILD_FORM = "http://openrosa.org/formdesigner/a591e5a20bf459c898bff3faacd552a3ebcc0f5d"
ADULT_FORM = "http://openrosa.org/formdesigner/60666f0dc7688fdef369947196722ff2f235101e"


class MVPExpressionSpec(JsonObject):
    type = TypeProperty('mvp_expression')

    def _treatment_place_name(self, form, doc):
        death_place = ""
        treatment_place_name = ""
        if form == NEONATE_FORM:
            try:
                treatment_place_name = doc['q1006_q1060']['q1023_q1039']['q1024']
            except KeyError:
                pass
        if form == CHILD_FORM:
            try:
                treatment_place_name = doc['q201-1114']['q1023-1039']['q1024']
            except KeyError:
                pass
        if form == ADULT_FORM:
            try:
                treatment_place_name = doc['q1006_q1060']['q1023_q1039']['q1024']
            except KeyError:
                pass

        return treatment_place_name

    def _death_place(self, form, doc):
        death_place = ""
        death_field_value = ""
        if form == NEONATE_FORM:
            try:
                death_field_value = int(doc['interview']['q306'])
            except KeyError:
                pass
        if form == CHILD_FORM:
            try:
                death_field_value = int(doc['q201-1114']['q305-402']['q306'])
            except KeyError:
                pass
        if form == ADULT_FORM:
            try:
                death_field_value = int(doc['interview']['q306'])
            except KeyError:
                pass

        if death_field_value:
            if death_field_value == 11:
                death_place = "Hospital"
            if death_field_value == 12:
                death_place = "Health clinic/post"
            if death_field_value == 14:
                death_place = "Home"
            if death_field_value == 13:
                death_place = "On route"
            if death_field_value == 90:
                death_place = "Dont Know"

        return death_place

    def _death_cause(self, form, doc):
        death_cause = ""
        if form == NEONATE_FORM:
            if doc.has_key('birth_asphyxia') and int(doc['birth_asphyxia']) == 1:
                death_cause += "Birth asphyxia <br>"
            if doc.has_key('birth_trauma') and int(doc['birth_trauma']) == 1:
                death_cause += "Birth trauma  <br>"
            if doc.has_key('congenital_abnormality') and int(doc['congenital_abnormality']) == 1:
                death_cause += "Congenital abnormality <br>"
            if doc.has_key('diarrhea_dysentery') and int(doc['diarrhea_dysentery']) == 1:
                death_cause += "Diarrhea/Dysentery <br>"
            if doc.has_key('low_birthweight_sev_malnutr_or_preterm') and int(doc['low_birthweight_sev_malnutr_or_preterm']) == 1:
                death_cause += "Low birthweight/Severe malnutrition/Preterm <br>"
            if doc.has_key('pneumonia_ari') and int(doc['pneumonia_ari']) == 1:
                death_cause += "Pneumonia/ari <br>"
            if doc.has_key('tetanus') and int(doc['tetanus']) == 1:
                death_cause += "Tetanus <br>"
            if len(death_cause) < 1:
                death_cause += "Unknown"

        if form == CHILD_FORM:
            if doc.has_key('Accident') and int(doc['Accident']) == 1:
                death_cause += "Child Accident <br>"
            if doc.has_key('Diarrhea_Dysentery_Any') and int(doc['Diarrhea_Dysentery_Any']) == 1:
                death_cause += "Any Diarrhea/Dysentry <br>"
            if doc.has_key('Diarrhea_Dysenter_Persistent') and int(doc['Diarrhea_Dysenter_Persistent']) == 1:
                death_cause += "Persistent Diarrhea_Dysentry <br>"
            if doc.has_key('Diarrhea_Acute') and int(doc['Diarrhea_Acute']) == 1:
                death_cause += "Acute Diarrhea <br>"
            if doc.has_key('Dysentery_Acute') and int(doc['Dysentery_Acute']) == 1:
                death_cause += "Acute Dysentry <br>"
            if doc.has_key('Malaria') and int(doc['Malaria']) == 1:
                death_cause += "Malaria <br>"
            if doc.has_key('Malnutrition') and int(doc['Malnutrition']) == 1:
                death_cause += "Malnutrition <br>"
            if doc.has_key('Measles') and int(doc['Measles']) == 1:
                death_cause += "Measles <br>"
            if doc.has_key('Meningitis') and int(doc['Meningitis']) == 1:
                death_cause += "Meningitis <br>"
            if doc.has_key('Pneumonia_ARI') and int(doc['Pneumonia_ARI']) == 1:
                death_cause += "Pneumonia/ari <br>"
            if len(death_cause) < 1:
                death_cause += "Unknown"

        if form == ADULT_FORM:
            if doc.has_key('Abortion') and int(doc['Abortion']) == 1:
                death_cause += "Abortion <br>"
            if doc.has_key('Accident') and int(doc['Accident']) == 1:
                death_cause += "Accident <br>"
            if doc.has_key('Antepartum_Haemorrhage') and int(doc['Antepartum_Haemorrhage']) == 1:
                death_cause += "Antepartum Haemorrhage <br>"
            if doc.has_key('Postpartum_Haemorrhage') and int(doc['Postpartum_Haemorrhage']) == 1:
                death_cause += "Postpartum Haemorrhage <br>"
            if doc.has_key('Eclampsia') and int(doc['Eclampsia']) == 1:
                death_cause += "Eclampsia <br>"
            if doc.has_key('Obstructed_Labour') and int(doc['Obstructed_Labour']) == 1:
                death_cause += "Obstructed Labour <br>"
            if doc.has_key('Puereral_Sepsis') and int(doc['Puereral_Sepsis']) == 1:
                death_cause += "Peural Sepsis <br>"
            if len(death_cause) < 1:
                death_cause += "Unknown"

        return death_cause

    def _treatment_providers(self, form, doc):
        treatment_providers = ""
        parent_node = ""
        if form == NEONATE_FORM:
            try:
                parent_node = doc['q1006_q1060']
            except KeyError:
                parent_node = False
        if form == CHILD_FORM:
            try:
                parent_node = doc['q201-1114']['q1001-1011']
            except KeyError:
                parent_node = False

        if parent_node:
            if parent_node.has_key('q1006_1') and int(parent_node['q1006_1']) == 1:
                treatment_providers += "CHW at home <br>"
            if parent_node.has_key('q1006_2') and int(parent_node['q1006_2']) == 1:
                treatment_providers += "Friend/Relative at home <br>"
            if parent_node.has_key('q1006_3') and int(parent_node['q1006_3']) == 1:
                treatment_providers += "Traditional healer <br>"
            if parent_node.has_key('q1006_4') and int(parent_node['q1006_4']) == 1:
                treatment_providers += "Health clinic/Post <br>"
            if parent_node.has_key('q1006_5') and int(parent_node['q1006_5']) == 1:
                treatment_providers += "Hospital <br>"
            if parent_node.has_key('q1006_6') and int(parent_node['q1006_6']) == 1:
                treatment_providers += "Pharmacy/drug seller/store <br>"
            if parent_node.has_key('q1006_7') and int(parent_node['q1006_7']) == 1:
                if parent_node.has_key('q1006_96'):
                    treatment_providers += parent_node['q1006_96']
                if parent_node.has_key('q1006_7_96'):
                    treatment_providers += parent_node['q1006_7_96']

        if form == ADULT_FORM:
            adult_answer = ""
            try:
                treatment_providers_choices = doc['interview']['q1006_q1060']['q1006']
            except KeyError:
                pass

            if len(adult_answer) > 0:
                choices = treatment_providers_choices.split(" ")
                for x in choices:
                    if int(x) == 1:
                        treatment_providers += "CHW at home <br>"
                    if int(x) == 2:
                        treatment_providers += "Friend/Relative at home <br>"
                    if int(x) == 3:
                        treatment_providers += "Traditional healer <br>"
                    if int(x) == 4:
                        treatment_providers += "Health clinic/Post <br>"
                    if int(x) == 5:
                        treatment_providers += "Hospital <br>"
                    if int(x) == 6:
                        treatment_providers += "Pharmacy/drug seller/store <br>"
                    if int(x) == 7:
                        try:
                            treatment_providers += doc['interview']['q1006_q1060']['q1006_7']
                        except KeyError:
                            pass
        return treatment_providers

    def __call__(self, item, context=None):

        docs = []

        docs.append({'mvp_death_place': self._death_place(item['xmlns'], item['form']),
                    'mvp_death_cause': self._death_cause(item['xmlns'], item['form']),
                    'mvp_treatment_place_name': self._treatment_place_name(item['xmlns'], item['form']),
                    'mvp_treatment_providers': self._treatment_providers(item['xmlns'], item['form'])})
        return docs


def mvp_expression(spec, context):
    wrapped = MVPExpressionSpec.wrap(spec)
    return wrapped
