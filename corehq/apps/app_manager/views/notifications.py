from django.utils.translation import gettext as _


def notify_form_opened(domain, couch_user, app_id, form_unique_id):
    message = _('This form has been opened for editing by {}.').format(couch_user.username)
    notify_event(domain, couch_user, app_id, form_unique_id, message)


def notify_form_changed(domain, couch_user, app_id, form_unique_id):
    message = _(
        'This form has been updated by {}. Reload the page to see the latest changes.'
    ).format(couch_user.username)
    notify_event(domain, couch_user, app_id, form_unique_id, message)


def notify_event(domain, couch_user, app_id, form_unique_id, message):
    # Do nothing. This function will be removed in https://github.com/dimagi/commcare-hq/pull/35881
    pass


def get_facility_for_form(domain, app_id, form_unique_id):
    """
    Gets the websocket facility (topic) for a particular form.
    """
    return '{}:{}:{}'.format(domain, app_id, form_unique_id)
