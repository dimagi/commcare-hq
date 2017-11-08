from __future__ import absolute_import
from corehq.apps.receiverwrapper.util import submit_form_locally


def form_requires_input(form):
    """
    Returns True if the form has at least one question that requires input
    """
    for question in form.get_questions([]):
        if question["tag"] not in ("trigger", "label", "hidden"):
            return True

    return False


def process_sms_form_complete(session, form, completed=True):
    result = submit_form_locally(form, session.domain,
        app_id=session.app_id, partial_submission=not completed)
    session.end(completed=completed)
    session.submission_id = result.xform.form_id
    session.save()
