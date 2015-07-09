from collections import defaultdict
import itertools
from django.dispatch import Signal
from corehq.apps.commtrack.const import REQUISITION_CASE_TYPE, RequisitionStatus
from corehq.apps.commtrack.models import CommtrackConfig
from corehq.apps.sms.api import send_sms_to_verified_number
from custom.openlmis.commtrack import requisition_receipt, requisition_approved
from custom.requisitions.models import RequisitionCase
from custom.requisitions.utils import get_notification_recipients, get_notification_message
from dimagi.utils import create_unique_filter


requisition_modified = Signal(providing_args=['cases'])


def send_notifications(xform, cases):
    # todo: this should be removed with requisitions. the only things that depend on it currently
    # are custom code
    # TODO: fix circular imports
    # for now the only notifications are for requisitions that were touched.
    # todo: if we wanted to include previously requested items we could do so
    # by either polling for other open requisitions here, or by ensuring that
    # they get touched by the commtrack case processing.
    requisitions = [RequisitionCase.wrap(case._doc) for case in cases if case.type == REQUISITION_CASE_TYPE]

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
    """
    Raise requisition events associated with cases
    """
    # todo: nothing calls this and it can be removed today, though openlmis code depends
    # on it being called during case processing
    requisition_cases = [RequisitionCase.wrap(c._doc) for c in cases if c.type == REQUISITION_CASE_TYPE]
    if requisition_cases and requisition_cases[0].requisition_status == RequisitionStatus.APPROVED:
        requisition_approved.send(sender=None, requisitions=requisition_cases)
    if requisition_cases and requisition_cases[0].requisition_status == RequisitionStatus.RECEIVED:
        requisition_receipt.send(sender=None, requisitions=requisition_cases)

    if requisition_cases and requisition_cases[0].requisition_status == RequisitionStatus.REQUESTED:
        requisition_modified.send(sender=None, cases=requisition_cases)
