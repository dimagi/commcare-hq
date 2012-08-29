from celery.log import get_task_logger
from celery.task import task
from couchdbkit.exceptions import ResourceNotFound
from corehq.apps.migration.post import post_data
from corehq.apps.migration.util.submission_xml import prepare_for_resubmission
from corehq.apps.users.models import CommCareUser
from couchforms.models import XFormInstance

logging = get_task_logger()

def _resubmit_form(url, form, user_id_mapping, owner_id_mapping):
    xml = prepare_for_resubmission(form.get_xml(), user_id_mapping, owner_id_mapping, salt=url)
    if form.get_id in xml:
        return "", ["New form still has old instanceID: %s" % form.get_id]
    results, errors = post_data(xml, url, submit_time=form.received_on)
    return results, errors

def check_form_domain(form, domain):
    if form.domain == domain:
        return True
    else:
        raise Exception("Form %s has mismatch between user's domain (%s) and form's domain (%s)" % (
            form.get_id, domain, form.domain
            ))

def forms_for_users(user_ids, domain):
    """
    The current implementation loads all form objects into memory and sorts them by date

    You could stream instead by going through all submissions sorted by date in couch
    and submitting the ones submitted by a user in user_mapping

    """

    all_forms = []

    for user_id in user_ids:
        user = CommCareUser.get_by_user_id(user_id, domain=domain)
        forms = user.get_forms()

        good_forms = []
        for form in forms:
            if check_form_domain(form, domain):
                good_forms.append(form)
        all_forms.extend(good_forms)

    all_forms.sort(key=lambda form: form.received_on)
    return all_forms

def forms_for_cases_for_users(user_ids, domain):
    all_form_ids = set()
    for user_id in user_ids:
        user = CommCareUser.get_by_user_id(user_id, domain=domain)
        all_form_ids.update(user.get_forms(wrap=False))
        for case in user.get_cases(last_submitter=True):
            all_form_ids.update(case.xform_ids)

    forms = []
    for id in all_form_ids:
        try:
            form = XFormInstance.get(id)
        except ResourceNotFound:
            continue
        else:
            if check_form_domain(form, domain):
                forms.append(form)
    forms.sort(key=lambda form: form.received_on)
    return forms

@task
def resubmit_for_users(url, user_id_mapping, group_id_mapping, domain):
    current_task = resubmit_for_users
    owner_id_mapping = {}
    owner_id_mapping.update(user_id_mapping)
    owner_id_mapping.update(group_id_mapping)

    n_errors = 0
    all_forms = forms_for_cases_for_users(user_id_mapping.keys(), domain)
    for i, form in enumerate(all_forms):
        logging.info('processing form %s' % form.get_id)
        results, errors = _resubmit_form(url, form, user_id_mapping, owner_id_mapping)
        if errors:
            n_errors += 1
            logging.error(errors)
        if current_task.request.id:
            current_task.update_state(
                state="PROGRESS",
                meta={"current": i, "errors": n_errors, "total": len(all_forms)}
            )
