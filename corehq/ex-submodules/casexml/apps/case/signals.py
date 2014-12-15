import warnings
from django.dispatch.dispatcher import Signal
from couchforms.signals import successful_form_received
from dimagi.utils.decorators.log_exception import log_exception
from couchforms.signals import xform_archived, xform_unarchived


def rebuild_form_cases(sender, xform, *args, **kwargs):
    from casexml.apps.case.xform import get_case_ids_from_form
    from casexml.apps.case.cleanup import rebuild_case
    for case_id in get_case_ids_from_form(xform):
        rebuild_case(case_id)


xform_archived.connect(rebuild_form_cases)
xform_unarchived.connect(rebuild_form_cases)

# any time a case is saved
case_post_save = Signal(providing_args=["case"])

# only when one or more cases are updated as the result of an xform submission
# the contract of this signal is that you should modify the form and cases in
# place but NOT save them. this is so that we can avoid multiple redundant writes
# to the database in a row. we may want to revisit this if it creates problems.
cases_received = Signal(providing_args=["xform", "cases"])
