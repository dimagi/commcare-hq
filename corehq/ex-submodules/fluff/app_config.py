from __future__ import absolute_import
from __future__ import unicode_literals
from django.apps import AppConfig
from django.db.models.signals import post_migrate
from fluff.signals import catch_signal


class FluffAppConfig(AppConfig):
    name = 'fluff'

    def ready(self):
        post_migrate.connect(catch_signal, sender=self)
