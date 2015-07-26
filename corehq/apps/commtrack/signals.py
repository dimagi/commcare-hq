from django.dispatch import Signal
from casexml.apps.case.signals import cases_received
from casexml.apps.case.xform import get_case_updates
from corehq.apps.commtrack import const
from corehq.apps.commtrack.const import is_supply_point_form
from corehq.apps.commtrack.models import SupplyPointCase
from corehq.apps.commtrack.util import bootstrap_commtrack_settings_if_necessary
from corehq.apps.domain.signals import commcare_domain_post_save
from corehq.util.soft_assert import soft_assert

supply_point_modified = Signal(providing_args=['supply_point', 'created'])


def attach_locations(xform, cases):
    """
    Given a received form and cases, update the location of that form to the location
    of its cases (if they have one).
    """
    # todo: this won't change locations if you are trying to do that via XML.
    # this is mainly just a performance thing so you don't have to do extra lookups
    # every time you touch a case
    if cases:
        location_ids = [getattr(case, 'location_id', None) for case in cases]
        unique_location_ids = set(filter(None, location_ids))
        if unique_location_ids:
            if len(unique_location_ids) != 1:
                error_message = (
                    'Submitted a commcare supply case with multiple locations '
                    'in a single form. This is currently not allowed. '
                    'Form id: {} case ids: {}'.format(
                        xform._id,
                        ', '.join([c._id for c in cases]),
                    )
                )
                _assert = soft_assert(to=['czue' + '@' + 'dimagi.com'], exponential_backoff=False)
                _assert(False, error_message)
                raise Exception(error_message)
            location_id = unique_location_ids.pop()
            xform.location_id = location_id


def raise_supply_point_events(xform, cases):
    supply_points = [SupplyPointCase.wrap(c._doc) for c in cases if c.type == const.SUPPLY_POINT_CASE_TYPE]
    case_updates = get_case_updates(xform)
    for sp in supply_points:
        created = any(filter(lambda update: update.id == sp._id and update.creates_case(), case_updates))
        supply_point_modified.send(sender=None, supply_point=sp, created=created)


def supply_point_processing(sender, xform, cases, **kwargs):
    if is_supply_point_form(xform):
        attach_locations(xform, cases)
        raise_supply_point_events(xform, cases)

cases_received.connect(supply_point_processing)


def bootstrap_commtrack_settings_if_necessary_signal(sender, **kwargs):
    bootstrap_commtrack_settings_if_necessary(kwargs['domain'])

commcare_domain_post_save.connect(bootstrap_commtrack_settings_if_necessary_signal)
