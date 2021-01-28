from django.apps import AppConfig


class HqWebAppConfig(AppConfig):
    name = 'corehq.apps.hqwebapp'

    def ready(self):
        # Ensure the login signal handlers have been loaded
        import corehq.apps.hqwebapp.login_handlers  # noqa
