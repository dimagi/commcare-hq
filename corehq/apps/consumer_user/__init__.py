from django.apps import AppConfig


class ConsumerUserAppConfig(AppConfig):
    name = 'corehq.apps.consumer_user'

    def ready(self):
        from corehq.apps.consumer_user.signals import connect_signals
        connect_signals()


default_app_config = 'corehq.apps.consumer_user.ConsumerUserAppConfig'
