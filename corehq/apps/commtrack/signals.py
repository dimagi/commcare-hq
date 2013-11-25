from collections import defaultdict
import itertools
from django.dispatch import Signal
from casexml.apps.case.signals import cases_received
from casexml.apps.case.xform import get_case_updates
from corehq.apps.commtrack import const
from corehq.apps.commtrack.const import is_commtrack_form, RequisitionStatus
from corehq.apps.commtrack.models import (RequisitionCase, SupplyPointProductCase,
        CommtrackConfig, SupplyPointCase)
from corehq.apps.commtrack.util import bootstrap_commtrack_settings_if_necessary
from corehq.apps.domain.signals import commcare_domain_post_save
from corehq.apps.locations.models import Location
from corehq.apps.sms.api import send_sms_to_verified_number
from dimagi.utils import create_unique_filter
from custom.openlmis.commtrack import requisition_receipt, requisition_approved


supply_point_modified = Signal(providing_args=['supply_point', 'created'])

requisition_modified = Signal(providing_args=['cases'])

def attach_locations(xform, cases):
    """
    Given a received form and cases, update the location of that form to the location
    of its cases (if they have one).
    """

    # todo: this won't change locations if you are trying to do that via XML.
    # this is mainly just a performance thing so you don't have to do extra lookups
    # every time you touch a case

    if cases:
        found_loc = None
        for case in cases:
            loc = None
            if not case.location_:
                if case.type == const.SUPPLY_POINT_CASE_TYPE:
                    loc_id = getattr(case, 'location_id', None)
                    if loc_id:
                        loc = Location.get(loc_id)
                        case.bind_to_location(loc)

                elif case.type == const.SUPPLY_POINT_PRODUCT_CASE_TYPE:
                    wrapped_case = SupplyPointProductCase.wrap(case._doc)
                    sp = wrapped_case.get_supply_point_case()
                    if sp and sp.location_:
                        loc = sp.location_
                        case.location_ = loc

                elif case.type == const.REQUISITION_CASE_TYPE:
                    req = RequisitionCase.wrap(case._doc)
                    prod = req.get_product_case()
                    if prod and prod.location_ and prod.location_ != case.location_:
                        case.location_ = prod.location_
                        case.save()

            if loc and found_loc and loc != found_loc:
                raise Exception(
                    'Submitted a commtrack case with multiple locations in a single form. '
                    'This is currently not allowed.'
                )
            found_loc = loc

        case = cases[0]
        if case.location_ is not None:
            # should probably store this in computed_
            xform.location_ = list(case.location_)


def send_notifications(xform, cases):
    # TODO: fix circular imports
    from corehq.apps.commtrack.requisitions import get_notification_recipients
    from corehq.apps.commtrack.requisitions import get_notification_message

    # for now the only notifications are for requisitions that were touched.
    # todo: if we wanted to include previously requested items we could do so
    # by either polling for other open requisitions here, or by ensuring that
    # they get touched by the commtrack case processing.
    requisitions = [RequisitionCase.wrap(case._doc) for case in cases if case.type == const.REQUISITION_CASE_TYPE]

    if requisitions:
        by_status = defaultdict(list)
        for r in requisitions:
            by_status[r.requisition_status].append(r)

        req_config = CommtrackConfig.for_domain(requisitions[0].domain).requisition_config
        # since each state transition might trigger a different person to be notified
        for s, reqs in by_status.items():
            next_action = req_config.get_next_action(RequisitionStatus.to_action_type(s))

            if next_action:
                # we could make this even more customizable by specifying it per requisition
                # but that would get even messier in terms of constructing the messages
                # so we'll just compose one message per status type now, and then send
                # it to everyone who should be notified.
                to_notify = filter(
                    create_unique_filter(lambda u: u._id),
                    itertools.chain(*(get_notification_recipients(next_action, r) for r in reqs))
                )

                msg = get_notification_message(next_action, reqs)
                for u in to_notify:
                    phone = u.get_verified_number()
                    if phone:
                        send_sms_to_verified_number(phone, msg)


def raise_events(xform, cases):
    supply_points = [SupplyPointCase.wrap(c._doc) for c in cases if c.type == const.SUPPLY_POINT_CASE_TYPE]
    case_updates = get_case_updates(xform)
    for sp in supply_points:
        created = any(filter(lambda update: update.id == sp._id and update.creates_case(), case_updates))
        supply_point_modified.send(sender=None, supply_point=sp, created=created)
    requisition_cases = [RequisitionCase.wrap(c._doc) for c in cases if c.type == const.REQUISITION_CASE_TYPE]
    if requisition_cases and requisition_cases[0].requisition_status is RequisitionStatus.APPROVED:
        requisition_approved.send(sender=None, requisitions=requisition_cases)
    if requisition_cases and requisition_cases[0].requisition_status is RequisitionStatus.RECEIVED:
        requisition_receipt.send(sender=None, requisitions=requisition_cases)

    requisition_cases = [RequisitionCase.wrap(c._doc) for c in cases if c.type == const.REQUISITION_CASE_TYPE]
    if requisition_cases:
        requisition_modified.send(sender=None, cases=requisition_cases)

def commtrack_processing(sender, xform, cases, **kwargs):
    if is_commtrack_form(xform):
        attach_locations(xform, cases)
        send_notifications(xform, cases)
        raise_events(xform, cases)


cases_received.connect(commtrack_processing)


def bootstrap_commtrack_settings_if_necessary_signal(sender, **kwargs):
    bootstrap_commtrack_settings_if_necessary(kwargs['domain'])

commcare_domain_post_save.connect(bootstrap_commtrack_settings_if_necessary_signal)
