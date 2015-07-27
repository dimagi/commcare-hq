from django.dispatch import Signal
from casexml.apps.case.signals import cases_received
from casexml.apps.case.xform import get_case_updates
from corehq.apps.commtrack import const
from corehq.apps.commtrack.const import is_supply_point_form
from corehq.apps.commtrack.models import SupplyPointCase
from corehq.apps.commtrack.util import bootstrap_commtrack_settings_if_necessary
from corehq.apps.domain.signals import commcare_domain_post_save


supply_point_modified = Signal(providing_args=['supply_point', 'created'])


def raise_supply_point_events(xform, cases):
    supply_points = [SupplyPointCase.wrap(c._doc) for c in cases if c.type == const.SUPPLY_POINT_CASE_TYPE]
    case_updates = get_case_updates(xform)
    for sp in supply_points:
        created = any(filter(lambda update: update.id == sp._id and update.creates_case(), case_updates))
        supply_point_modified.send(sender=None, supply_point=sp, created=created)


def supply_point_processing(sender, xform, cases, **kwargs):
    if is_supply_point_form(xform):
        raise_supply_point_events(xform, cases)

cases_received.connect(supply_point_processing)


def bootstrap_commtrack_settings_if_necessary_signal(sender, **kwargs):
    bootstrap_commtrack_settings_if_necessary(kwargs['domain'])

commcare_domain_post_save.connect(bootstrap_commtrack_settings_if_necessary_signal)
