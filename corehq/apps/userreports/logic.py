
# operators
# todo: copy pasted from fluff.calculators.xforms
EQUAL = lambda input, reference: input == reference
NOT_EQUAL = lambda input, reference: input != reference
IN = lambda input, reference_list: input in reference_list
IN_MULTISELECT = lambda input, reference: reference in (input or '').split(' ')
ANY = lambda input, reference: bool(input)
SKIPPED = lambda input, reference: input is None

