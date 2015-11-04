from corehq.apps.receiverwrapper import submit_form_locally


def form_requires_input(form):
    """
    Returns True if the form has at least one question that requires input
    """
    for question in form.get_questions([]):
        if question["tag"] not in ("trigger", "label", "hidden"):
            return True

    return False


def process_sms_form_complete(session, form, completed):
    resp, xform, cases = submit_form_locally(form, session.domain, app_id=session.app_id)
    session.end(completed=completed)
    session.submission_id = xform.get_id
    session.save()

    if not completed:
        xform.partial_submission = True
    xform.survey_incentive = session.survey_incentive
    xform.save()
