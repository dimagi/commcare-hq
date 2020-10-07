from django.apps import AppConfig

class SettingsAppConfig(AppConfig):
    name = 'corehq.apps.settings'

    def ready(self):
        from elevate.signals import grant
        from django.contrib.auth.signals import user_logged_in

        # Remove the signal that was automatically connected by elevate at startup
        # Without this, users are automatically upgraded to sudo on login
        user_logged_in.disconnect(grant)