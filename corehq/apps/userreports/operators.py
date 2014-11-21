# operators
# todo: copy pasted from fluff.calculators.xforms
from corehq.apps.userreports.exceptions import BadSpecError

EQUAL = lambda input, reference: input == reference
NOT_EQUAL = lambda input, reference: input != reference
IN = lambda input, reference_list: input in reference_list
IN_MULTISELECT = lambda input, reference: reference in (input or '').split(' ')


OPERATORS = {
    'eq': EQUAL,
    'not_eq': NOT_EQUAL,
    'in': IN,
    'in_multi': IN_MULTISELECT,
}

def get_operator(slug=''):
    try:
        return OPERATORS[slug.lower()]
    except KeyError:
        raise BadSpecError('{0} is not a valid operator. Choices are {1}'.format(
            slug,
            ', '.join(OPERATORS.keys()),
        ))
