from memoized import memoized

from corehq.apps.user_importer.validation import RoleValidator


class AdminInvitesUserValidator():
    def __init__(self, domain, upload_user):
        self.domain = domain
        self.upload_user = upload_user

    @property
    @memoized
    def roles_by_name(self):
        from corehq.apps.users.views.utils import get_editable_role_choices
        return {role[1]: role[0] for role in get_editable_role_choices(self.domain, self.upload_user,
                                                  allow_admin_role=True)}

    def validate_role(self, role):
        spec = {'role': role}
        return RoleValidator(self.domain, self.roles_by_name()).validate_spec(spec)
