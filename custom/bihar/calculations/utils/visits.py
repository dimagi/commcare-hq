from __future__ import absolute_import
import logging
from custom.bihar.calculations.utils import xmlns


VISIT_TYPES = {
    'bp': xmlns.BP,
    'del': xmlns.DELIVERY,
    'pnc': xmlns.PNC,
    'eb': xmlns.EBF,
    'cf': xmlns.CF,
    'reg': xmlns.REGISTRATION,
}


def visit_is(action, visit_type):
    """
    for a given action returns whether it's a visit of the type
    """
    assert visit_type in VISIT_TYPES, 'Unknown visit type %r not in %r' % (
        visit_type,
        VISIT_TYPES
    )
    actual_visit_type = action.updated_unknown_properties.get('last_visit_type')

    if (action.xform_xmlns and actual_visit_type in VISIT_TYPES
            and VISIT_TYPES[actual_visit_type] != action.xform_xmlns):
        # make sure it's not just because this is a manual case reassignment
        # or some other HQ-submitted system form
        if action.xform_xmlns not in list(VISIT_TYPES.values()):
            return False
        logging.error('last_visit_type is %r but xmlns is not %r: %r' % (
            actual_visit_type,
            VISIT_TYPES[actual_visit_type],
            action.to_json()
        ))

    return actual_visit_type == visit_type


def has_visit(case, type):
    """
    returns whether a visit of a type exists in the case
    """
    return len([a for a in case.actions if visit_is(a, type)]) > 0
