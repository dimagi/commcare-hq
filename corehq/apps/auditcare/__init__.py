from django.apps import AppConfig
from django.contrib.auth.signals import (
    user_logged_in,
    user_logged_out,
    #user_login_failed,
)


class AuditcareConfig(AppConfig):
    name = __name__

    def ready(self):
        from .models import audit_login, audit_logout
        user_logged_in.connect(audit_login)
        user_logged_out.connect(audit_logout)
        #user_login_failed.connect(audit_login_failed)  FIXME
