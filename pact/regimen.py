import pdb
from pact.enums import DAY_SLOTS_BY_TIME, PACT_REGIMEN_CHOICES, DAY_SLOTS_BY_IDX, DOT_ART, DOT_NONART, CASE_ART_REGIMEN_PROP, CASE_NONART_REGIMEN_PROP

#def calculate_regimen_caseblock(self):
#    """
#    Forces all labels to be reset back to the labels set on the patient document.
#
#    patient document trumps casedoc in this case.
#    """
#    update_ret = {}
#    for prop_fmt in ['dot_a_%s', 'dot_n_%s']:
#        if prop_fmt[4] == 'a':
#            code_arr = get_regimen_code_arr(self.art_regimen)
#            update_ret['artregimen'] = str(len(code_arr)) if len(code_arr) > 0 else ""
#        elif prop_fmt[4] == 'n':
#            code_arr = get_regimen_code_arr(self.non_art_regimen)
#            update_ret['nonartregimen'] = str(len(code_arr)) if len(code_arr) > 0 else ""
#        digit_strings = ["zero", 'one', 'two', 'three','four']
#        for x in range(1,5):
#            prop_prop = prop_fmt % digit_strings[x]
#            if x > len(code_arr):
#                update_ret[prop_prop] = ''
#            else:
#                update_ret[prop_prop] = str(code_arr[x-1])
#    return update_ret

type_keys = {DOT_ART: 'dot_a_%s', DOT_NONART: 'dot_n_%s'}
digit_strings = ['one', 'two', 'three', 'four']

def regimen_dict_from_choice(key_type, regimen_string):
    """
    Given a regimen string, "morning,noon,evening" return a dict of the appropriate update values
    of the casedoc of this representation

    key_type is ART or NONART

    so if art will return 'artregimen': <int>, "dot_a_one": 0, "dot_a_two": "1", etc
    if nonartregimen it'll be 'nonartregimen' and dot_n_one, etc.
    """

    assert key_type in type_keys.keys(), 'the key_type must be ART or NONART'

    #ensure regimen_string is in PACT_REGIMEN_CHOICES_DICT
    #get integer day slot from DAY_SLOTS_BY_TIME[str]
    regimen_split = regimen_string.split(',')
    regimen_freq = len(regimen_split)
    day_key_prefix = type_keys[key_type]
    if key_type == DOT_ART:
        key_type_string = CASE_ART_REGIMEN_PROP
    elif key_type == DOT_NONART:
        key_type_string = CASE_NONART_REGIMEN_PROP
    ret = { key_type_string: str(regimen_freq) }
    for x in range(0, 4):
        if x < len(regimen_split):
            ret[day_key_prefix % digit_strings[x]] = str(DAY_SLOTS_BY_TIME.get(regimen_split[x], None))
        else:
            ret[day_key_prefix % digit_strings[x]] = ""
    return ret


def regimen_string_from_doc(drug_type, doc_dict):
    """
    For a dict of doc properties and a given drug_type (ART, NONART), calculate/confirm the
    regimen string of the times of doses.
    """
    assert drug_type in type_keys.keys(), "the drug type must be art or nonart"
    prefix = type_keys[drug_type]

    if drug_type == DOT_ART:
        try:
            freq = int(doc_dict.get(CASE_ART_REGIMEN_PROP, ''))
        except ValueError:
            return None
    elif drug_type == DOT_NONART:
        try:
            freq = int(doc_dict.get(CASE_NONART_REGIMEN_PROP, ''))
        except ValueError:
            return None

    props = []
    for digit in digit_strings:
        key = prefix % digit
        prop = doc_dict.get(key, '')
        if prop != '' and prop is not None:
            props.append(int(prop))

    return string_from_regimen_props(freq, props=props)



def string_from_regimen_props(freq, props=[]):
    """
    For a given set of properties, (dot_a_one, etc...)

    return the comma separated string of the regimen frequency/dose times
    morning,noon,evening...etc
    """
    str_props = []
    for prop in props:
        if prop == "" or prop is None:
            break
        str_props.append(DAY_SLOTS_BY_IDX[prop])

    if len(str_props) == freq:
        return ','.join(str_props)
    else:
        raise Exception("Error, frequency %d given does not match properties %s" % (freq, props))



