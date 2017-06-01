from django.apps import AppConfig


class MessagingAppConfig(AppConfig):
    name = 'corehq.messaging'

    def ready(self):
        from corehq.messaging.signals import connect_signals
        connect_signals()


default_app_config = 'corehq.messaging.MessagingAppConfig'
