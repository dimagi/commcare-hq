# operators
# todo: copy pasted from fluff.calculators.xforms
from corehq.apps.userreports.exceptions import BadSpecError

EQUAL = lambda input, reference: input == reference
NOT_EQUAL = lambda input, reference: input != reference
IN_MULTISELECT = lambda input, reference: reference in (input or '').split(' ')
ANY_IN_MULTISELECT = lambda input, reference: any([subval in (input or '').split(' ') for subval in reference])
LESS_THAN = lambda input, reference: input < reference
LESS_THAN_EQUAL = lambda input, reference: input <= reference
GREATER_THAN = lambda input, reference: input > reference
GREATER_THAN_EQUAL = lambda input, reference: input >= reference


def IN(input, reference_list):
    try:
        return input in reference_list
    except TypeError:
        return False


OPERATORS = {
    'eq': EQUAL,
    'not_eq': NOT_EQUAL,
    'in': IN,
    'in_multi': IN_MULTISELECT,
    'any_in_multi': ANY_IN_MULTISELECT,
    'lt': LESS_THAN,
    'lte': LESS_THAN_EQUAL,
    'gt': GREATER_THAN,
    'gte': GREATER_THAN_EQUAL,
}


def get_operator(slug):
    try:
        return OPERATORS[slug.lower()]
    except KeyError:
        raise BadSpecError('{0} is not a valid operator. Choices are {1}'.format(
            slug,
            ', '.join(OPERATORS.keys()),
        ))
