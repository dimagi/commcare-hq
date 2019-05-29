from __future__ import absolute_import
from __future__ import unicode_literals
from django.dispatch.dispatcher import Signal
from corehq.form_processor.models import FormArchiveRebuild
from couchforms.signals import xform_archived, xform_unarchived


def rebuild_form_cases(sender, xform, *args, **kwargs):
    if not kwargs.get('rebuild_cases'):
        return
    from casexml.apps.case.cleanup import rebuild_case_from_forms

    domain = xform.domain
    case_ids = xform.case_ids()
    detail = FormArchiveRebuild(form_id=xform.form_id, archived=xform.is_archived)
    for case_id in case_ids:
        rebuild_case_from_forms(domain, case_id, detail)


xform_archived.connect(rebuild_form_cases)
xform_unarchived.connect(rebuild_form_cases)

# any time a case is saved
case_post_save = Signal(providing_args=["case"])

# only when one or more cases are updated as the result of an xform submission
# the contract of this signal is that you should modify the form and cases in
# place but NOT save them. this is so that we can avoid multiple redundant writes
# to the database in a row. we may want to revisit this if it creates problems.
cases_received = Signal(providing_args=["xform", "cases"])
