from django.dispatch import Signal
from casexml.apps.case.signals import cases_received

location_created = Signal(providing_args=['loc'])
location_edited = Signal(providing_args=['loc', 'moved'])


def attach_location_to_xform(sender, xform, cases, **kwargs):
    """
    Given a received form and cases, update the location of that form to the location
    of its cases (if they have one).
    """
    if cases:
        # NOTE: this only checks the first case by design, though we may want to switch
        # it to check all cases. not sure what the behavior should be if there were
        # cases with conflicting locations inside the form
        case = cases[0]
        if case.location_ is not None:
            # should probably store this in computed_
            xform.location_ = list(case.location_)

cases_received.connect(attach_location_to_xform)
