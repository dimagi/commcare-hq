from corehq.apps.userreports.specs import TypeProperty
from dimagi.ext.jsonobject import JsonObject

NEONATE_FORM = "http://openrosa.org/formdesigner/5cd541d5a1034f02c922dc888416148a89b85ffa"
CHILD_FORM = "http://openrosa.org/formdesigner/a591e5a20bf459c898bff3faacd552a3ebcc0f5d"
ADULT_FORM = "http://openrosa.org/formdesigner/60666f0dc7688fdef369947196722ff2f235101e"


class TreatmentPlaceExpressionSpec(JsonObject):
    type = TypeProperty('mvp_treatment_place_name')

    def __call__(self, item, context=None):
        doc = item['form']
        form = item['xmlns']
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


class DeathPlaceExpressionSpec(JsonObject):
    type = TypeProperty('mvp_death_place')

    def __call__(self, item, context=None):
        doc = item['form']
        form = item['xmlns']
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


class MedicalCauseExpressionSpec(JsonObject):
    type = TypeProperty('mvp_medical_cause')

    def __call__(self, item, context=None):
        doc = item['form']
        form = item['xmlns']
        death_cause = ""
        if form == NEONATE_FORM:
            if 'birth_asphyxia' in doc and int(doc['birth_asphyxia']) == 1:
                death_cause += "Birth asphyxia <br>"
            if 'birth_trauma' in doc and int(doc['birth_trauma']) == 1:
                death_cause += "Birth trauma  <br>"
            if 'congenital_abnormality' in doc and int(doc['congenital_abnormality']) == 1:
                death_cause += "Congenital abnormality <br>"
            if 'diarrhea_dysentery' in doc and int(doc['diarrhea_dysentery']) == 1:
                death_cause += "Diarrhea/Dysentery <br>"
            if 'low_birthweight_sev_malnutr_or_preterm' in doc and \
               int(doc['low_birthweight_sev_malnutr_or_preterm']) == 1:
                    death_cause += "Low birthweight/Severe malnutrition/Preterm <br>"
            if 'pneumonia_ari' in doc and int(doc['pneumonia_ari']) == 1:
                death_cause += "Pneumonia/ari <br>"
            if 'tetanus' in doc and int(doc['tetanus']) == 1:
                death_cause += "Tetanus <br>"
            if len(death_cause) < 1:
                death_cause += "Unknown"

        if form == CHILD_FORM:
            if 'Accident' in doc and int(doc['Accident']) == 1:
                death_cause += "Child Accident <br>"
            if 'Diarrhea_Dysentery_Any' in doc and int(doc['Diarrhea_Dysentery_Any']) == 1:
                death_cause += "Any Diarrhea/Dysentry <br>"
            if 'Diarrhea_Dysenter_Persistent' in doc and int(doc['Diarrhea_Dysenter_Persistent']) == 1:
                death_cause += "Persistent Diarrhea_Dysentry <br>"
            if 'Diarrhea_Acute' in doc and int(doc['Diarrhea_Acute']) == 1:
                death_cause += "Acute Diarrhea <br>"
            if 'Dysentery_Acute' in doc and int(doc['Dysentery_Acute']) == 1:
                death_cause += "Acute Dysentry <br>"
            if 'Malaria' in doc and int(doc['Malaria']) == 1:
                death_cause += "Malaria <br>"
            if 'Malnutrition' in doc and int(doc['Malnutrition']) == 1:
                death_cause += "Malnutrition <br>"
            if 'Measles' in doc and int(doc['Measles']) == 1:
                death_cause += "Measles <br>"
            if 'Meningitis' in doc and int(doc['Meningitis']) == 1:
                death_cause += "Meningitis <br>"
            if 'Pneumonia_ARI' in doc and int(doc['Pneumonia_ARI']) == 1:
                death_cause += "Pneumonia/ari <br>"
            if len(death_cause) < 1:
                death_cause += "Unknown"

        if form == ADULT_FORM:
            if 'Abortion' in doc and int(doc['Abortion']) == 1:
                death_cause += "Abortion <br>"
            if 'Accident' in doc and int(doc['Accident']) == 1:
                death_cause += "Accident <br>"
            if 'Antepartum_Haemorrhage' in doc and int(doc['Antepartum_Haemorrhage']) == 1:
                death_cause += "Antepartum Haemorrhage <br>"
            if 'Postpartum_Haemorrhage' in doc and int(doc['Postpartum_Haemorrhage']) == 1:
                death_cause += "Postpartum Haemorrhage <br>"
            if 'Eclampsia' in doc and int(doc['Eclampsia']) == 1:
                death_cause += "Eclampsia <br>"
            if 'Obstructed_Labour' in doc and int(doc['Obstructed_Labour']) == 1:
                death_cause += "Obstructed Labour <br>"
            if 'Puereral_Sepsis' in doc and int(doc['Puereral_Sepsis']) == 1:
                death_cause += "Peural Sepsis <br>"
            if len(death_cause) < 1:
                death_cause += "Unknown"

        return death_cause


class TreatmentProviderExpressionSpec(JsonObject):
    type = TypeProperty('mvp_treatment_provider_name')

    def __call__(self, item, context=None):
        doc = item['form']
        form = item['xmlns']
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
            if 'q1006_1' in parent_node and int(parent_node['q1006_1']) == 1:
                treatment_providers += "CHW at home <br>"
            if 'q1006_2' in parent_node and int(parent_node['q1006_2']) == 1:
                treatment_providers += "Friend/Relative at home <br>"
            if 'q1006_3' in parent_node and int(parent_node['q1006_3']) == 1:
                treatment_providers += "Traditional healer <br>"
            if 'q1006_4' in parent_node and int(parent_node['q1006_4']) == 1:
                treatment_providers += "Health clinic/Post <br>"
            if 'q1006_5' in parent_node and int(parent_node['q1006_5']) == 1:
                treatment_providers += "Hospital <br>"
            if 'q1006_6' in parent_node and int(parent_node['q1006_6']) == 1:
                treatment_providers += "Pharmacy/drug seller/store <br>"
            if 'q1006_7' in parent_node and int(parent_node['q1006_7']) == 1:
                if 'q1006_96' in parent_node:
                    treatment_providers += parent_node['q1006_96']
                if 'q1006_7_96' in parent_node:
                    treatment_providers += parent_node['q1006_7_96']

        if form == ADULT_FORM:
            treatment_providers_choices = ""
            try:
                treatment_providers_choices = doc['interview']['q1006_q1060']['q1006']
            except KeyError:
                pass

            if len(treatment_providers_choices) > 0:
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


class NoTreatmentReasonExpressionSpec(JsonObject):
    type = TypeProperty('mvp_no_treatment_reason')

    def __call__(self, item, context=None):
        doc = item['form']
        form = item['xmlns']
        no_treatment_reason = ""
        if form == NEONATE_FORM:
            try:
                no_treatment_node = doc['interview']['q801_q1005']
            except KeyError:
                no_treatment_node = False
        if form == CHILD_FORM:
            try:
                no_treatment_node = doc['q201-1114']['q1001-1011']
            except KeyError:
                no_treatment_node = False
        if form == ADULT_FORM:
            try:
                no_treatment_node = doc['interview']
            except KeyError:
                no_treatment_node = False

        if no_treatment_node and 'q1005' in no_treatment_node and len(no_treatment_node['q1005']) > 0:
            choices = no_treatment_node['q1005'].split(" ")
            for x in choices:
                if int(x) == 1:
                    no_treatment_reason += "Personal/ religious objection <br>"
                if int(x) == 2:
                    no_treatment_reason += "No means of transport <br>"
                if int(x) == 3:
                    no_treatment_reason += "No money for transport <br>"
                if int(x) == 4:
                    no_treatment_reason += "No phone to call transport <br>"
                if int(x) == 5:
                    no_treatment_reason += "No money for phone to call transport <br>"
                if int(x) == 6:
                    no_treatment_reason += "Transport was too late <br>"
                if int(x) == 7:
                    no_treatment_reason += "No money to pay for consult <br>"
                if int(x) == 8:
                    no_treatment_reason += "No money to pay for drugs <br>"
                if int(x) == 90:
                    no_treatment_reason += "Don't know <br>"
                if int(x) == 96:
                    try:
                        no_treatment_reason += no_treatment_node['q1005_96']
                    except KeyError:
                        pass

        return no_treatment_reason


def treatment_provider_name_expression(spec, context):
    wrapped = TreatmentProviderExpressionSpec.wrap(spec)
    return wrapped


def death_place_expression(spec, context):
    wrapped = DeathPlaceExpressionSpec.wrap(spec)
    return wrapped


def treatment_place_name_expression(spec, context):
    wrapped = TreatmentPlaceExpressionSpec.wrap(spec)
    return wrapped


def no_treatment_reason_expression(spec, context):
    wrapped = NoTreatmentReasonExpressionSpec.wrap(spec)
    return wrapped


def medical_cause_expression(spec, context):
    wrapped = MedicalCauseExpressionSpec.wrap(spec)
    return wrapped
