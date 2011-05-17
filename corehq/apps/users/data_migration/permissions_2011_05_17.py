from corehq.apps.users.models import CouchUser, Permissions

def run():
    users = CouchUser.view('users/all_users', include_docs=True)
    for user in users:
        save = False
        for dm in user.web_account.domain_memberships:
            if not dm.is_admin:
                save = True
                user.set_permission(dm.domain, Permissions.EDIT_APPS, True, save=False)
        if save:
            user.save()