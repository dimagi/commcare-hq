from unittest.mock import patch

from django.test import RequestFactory
from testil import Regex

from ..forms import AdminInvitesUserForm
from corehq.apps.users.models import WebUser, Invitation


patch_query = patch.object(
    AdminInvitesUserForm,
    "_user_has_permission_to_access_locations",
    lambda *ignore: True,
)

mock_couch_user = WebUser(
    username="testuser",
    _id="user123",
    domain="test-domain",
)

mock_existing_user = WebUser(
    username="existinguser@test.com",
    _id="existinguser123",
    domain="test-domain",
)

mock_existing_pending_invitation = Invitation(
    email="existinguser@test.com",
    domain="test-domain",
)


@patch_query
@patch("corehq.apps.users.models.WebUser.get_by_username", return_value=None)
@patch("corehq.apps.users.models.WebUser.by_domain")
@patch("corehq.apps.users.models.Invitation.by_domain")
def test_minimal_valid_form(mock_web_user, mock_by_domain, mock_invitation):
    form = create_form()
    assert form.is_valid(), form.errors


@patch_query
@patch("corehq.apps.users.models.WebUser.get_by_username", return_value=None)
@patch("corehq.apps.users.models.WebUser.by_domain")
@patch("corehq.apps.users.models.Invitation.by_domain", return_value=[mock_existing_pending_invitation])
def test_form_is_invalid_when_invite_existing_email_with_case_mismatch(
    mock_web_user, mock_by_domain, mock_invitation
):
    form = create_form(
        {"email": "existinguser@TEST.com"},
    )

    msg = "this email address is already in this project"
    assert not form.is_valid()
    assert form.errors["email"] == [Regex(msg)], form.errors


@patch_query
@patch("corehq.apps.users.models.WebUser.get_by_username", return_value=None)
@patch("corehq.apps.users.models.WebUser.by_domain", return_value=[mock_existing_user])
@patch("corehq.apps.users.models.Invitation.by_domain")
def test_form_is_invalid_when_existing_user_with_case_mismatch(mock_web_user, mock_by_domain, mock_invitation):
    form = create_form(
        {"email": "existinguser@TEST.com"},
    )

    msg = "this email address is already in this project"
    assert not form.is_valid()
    assert form.errors["email"] == [Regex(msg)], form.errors


@patch_query
@patch("corehq.apps.users.models.WebUser.get_by_username", return_value=mock_couch_user)
@patch("corehq.apps.users.models.WebUser.by_domain")
@patch("corehq.apps.users.models.Invitation.by_domain")
def test_form_is_invalid_when_invite_deactivated_user(mock_web_user, mock_by_domain, mock_invitation):
    mock_web_user.is_active = False
    form = create_form(
        {"email": "test@TEST.com"},
    )

    msg = "A user with this email address is deactivated."
    assert not form.is_valid()
    assert form.errors["email"] == [Regex(msg)], form.errors


def create_form(data=None, **kw):
    form_defaults = {"email": "test@test.com", "role": "admin"}
    request = RequestFactory().post("/", form_defaults | (data or {}))
    request.couch_user = mock_couch_user
    defaults = {
        "domain": "test",
        "request": request,
        "role_choices": [("admin", "admin")],
    }
    return AdminInvitesUserForm(request.POST, **(defaults | kw))
