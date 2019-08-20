from __future__ import absolute_import

from __future__ import unicode_literals

from functools import wraps

import six
from couchdbkit import ResourceConflict
from django.utils.translation import ugettext as _

from casexml.apps.case.xml import V2
from casexml.apps.phone.restore import RestoreConfig, RestoreParams
from corehq.apps.domain.auth import get_username_and_password_from_request, determine_authtype_from_request
from corehq.apps.domain.models import Domain
from corehq.apps.locations.permissions import user_can_access_other_user
from corehq.apps.users.decorators import ensure_active_user_by_username
from corehq.apps.users.models import CommCareUser
from dimagi.utils.logging import notify_exception
from dimagi.utils.web import json_response
from .exceptions import RestorePermissionDenied
from .models import DemoUserRestore


def turn_off_demo_mode(commcare_user):
    """
    Turns demo mode OFF for commcare_user and deletes existing demo restore
    """

    delete_demo_restore_for_user(commcare_user)
    commcare_user.demo_restore_id = None
    commcare_user.is_demo_user = False
    commcare_user.save()


def turn_on_demo_mode(commcare_user, domain):
    """
    Turns demo mode ON for commcare_user, and resets restore to latest
    """
    try:
        # the order of following two is important, because the restore XML will contain
        # <data user_type='demo'> only if commcare_user.is_demo_user is True
        commcare_user.is_demo_user = True
        reset_demo_user_restore(commcare_user, domain)
        return {'errors': []}
    except Exception as e:
        notify_exception(None, message=six.text_type(e))
        return {'errors': [
            _("Something went wrong in creating restore for the user. Please try again or report an issue")
        ]}


def reset_demo_user_restore(commcare_user, domain):
    """
    Updates demo restore for the demo commcare_user
    """
    assert commcare_user.domain == domain

    # if there is a restore already, delete it
    delete_demo_restore_for_user(commcare_user)
    # get latest restore
    restore = RestoreConfig(
        project=Domain.get_by_name(domain),
        restore_user=commcare_user.to_ota_restore_user(),
        params=RestoreParams(version=V2),
    ).get_payload().as_file()
    demo_restore = DemoUserRestore.create(commcare_user._id, restore, domain)

    # Set reference to new restore
    try:
        commcare_user.demo_restore_id = demo_restore.id
        commcare_user.save()
    except ResourceConflict:
        # If CommCareUser.report_metadata gets updated by sync log pillow, after a restore is
        #   generated or for any other reason, there will be a DocumentUpdate conflict
        commcare_user = CommCareUser.get(commcare_user.get_id)
        commcare_user.is_demo_user = True
        commcare_user.demo_restore_id = demo_restore.id
        commcare_user.save()


def delete_demo_restore_for_user(commcare_user):
    # Deletes the users' current demo restore object
    # Caller should save the user doc
    old_restore_id = commcare_user.demo_restore_id
    if old_restore_id:
        old_restore = DemoUserRestore.objects.get(id=old_restore_id)
        old_restore.delete()


def demo_user_restore_response(commcare_user):
    assert commcare_user.is_commcare_user()

    restore = DemoUserRestore.objects.get(id=commcare_user.demo_restore_id)
    return restore.get_restore_http_response()


def demo_restore_date_created(commcare_user):
    """
    Returns date of last restore for the demo commcare user
    """
    if commcare_user.is_demo_user:
        restore = DemoUserRestore.objects.get(id=commcare_user.demo_restore_id)
        if restore:
            return restore.timestamp_created


def is_permitted_to_restore(domain, couch_user, as_user_obj):
    """
    This function determines if the couch_user is permitted to restore
    for the domain and/or as_user_obj
    :param domain: Domain of restore
    :param couch_user: The couch user attempting authentication
    :param as_user_obj: The user that the couch_user is attempting to get
        a restore for. If None will get restore of the couch_user.
    :returns: a tuple - first a boolean if the user is permitted,
        secondly a message explaining why a user was rejected if not permitted
    """
    try:
        _ensure_valid_domain(domain, couch_user)
        if as_user_obj is not None and not _restoring_as_yourself(couch_user, as_user_obj):
            _ensure_valid_restore_as_user(domain, couch_user, as_user_obj)
            _ensure_accessible_location(domain, couch_user, as_user_obj)
            _ensure_edit_data_permission(domain, couch_user)
    except RestorePermissionDenied as e:
        return False, six.text_type(e)
    else:
        return True, None


def _restoring_as_yourself(couch_user, as_user_obj):
    return as_user_obj and couch_user._id == as_user_obj._id


def _ensure_valid_domain(domain, couch_user):
    if not couch_user.is_member_of(domain):
        raise RestorePermissionDenied(_("{} was not in the domain {}").format(couch_user.username, domain))


def _ensure_valid_restore_as_user(domain, couch_user, as_user_obj):
    if not as_user_obj.is_member_of(domain):
        raise RestorePermissionDenied(_("{} was not in the domain {}").format(as_user_obj.username, domain))


def _ensure_accessible_location(domain, couch_user, as_user_obj):
    if not user_can_access_other_user(domain, couch_user, as_user_obj):
        raise RestorePermissionDenied(
            _('Restore user {} not in allowed locations').format(as_user_obj.username)
        )


def _ensure_edit_data_permission(domain, couch_user):
    if couch_user.is_commcare_user() and not couch_user.has_permission(domain, 'edit_commcare_users'):
        raise RestorePermissionDenied(
            _('{} does not have permission to edit commcare users').format(couch_user.username)
        )


def get_restore_user(domain, couch_user, as_user_obj):
    """
    This will retrieve the restore_user from the couch_user or the as_user_obj
    if specified
    :param domain: Domain of restore
    :param couch_user: The couch user attempting authentication
    :param as_user_obj: The user that the couch_user is attempting to get
        a restore user for. If None will get restore of the couch_user.
    :returns: An instance of OTARestoreUser
    """
    couch_restore_user = as_user_obj or couch_user

    if couch_restore_user.is_commcare_user():
        return couch_restore_user.to_ota_restore_user()
    elif couch_restore_user.is_web_user():
        return couch_restore_user.to_ota_restore_user(domain)
    else:
        return None


def handle_401_response(f):
    """
    Generic decorator to return better notice/message about why the authentication failed. Currently taking care of
    only basic auth for inactive or deleted mobile user but should/can be extended for other auth methods and cases
    :return json response with apt error_code in app_string and default response in english for missing
    translations and status_code as 406(unacceptable), similar code needed different from 401
    """
    @wraps(f)
    def _inner(request, domain, *args, **kwargs):
        response = f(request, domain, *args, **kwargs)
        if response.status_code == 401:
            auth_type = determine_authtype_from_request(request)
            if auth_type and auth_type == 'basic':
                username, _ = get_username_and_password_from_request(request)
                if username:
                    valid, message, error_code = ensure_active_user_by_username(username)
                    if not valid:
                        return json_response({
                            "error": error_code,
                            "default_response": message
                        }, status_code=406)

        return response
    return _inner
