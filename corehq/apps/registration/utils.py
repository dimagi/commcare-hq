from datetime import datetime
from corehq.apps.users.models import WebUser

def activate_new_user(form):
    username = form.cleaned_data['email']
    password = form.cleaned_data['password']
    full_name = form.cleaned_data['full_name']

    new_user = WebUser.create(None, username, password, is_admin=True)
    new_user.first_name = full_name[0]
    new_user.last_name = full_name[1]
    new_user.email = username

    new_user.is_staff = False # Can't log in to admin site
    new_user.is_active = True
    new_user.is_superuser = False
    new_user.last_login = datetime.utcnow()
    new_user.date_joined = datetime.utcnow()
    new_user.save()
