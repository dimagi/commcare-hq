# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function
from __future__ import unicode_literals

from django.core.management.base import BaseCommand
from corehq.apps.app_manager.models import LinkedApplication, Application


class Command(BaseCommand):
    @staticmethod
    def _iter_linked_apps():
        app_ids = [
            result['id'] for result in Application.get_db().view(
                'app_manager/applications',
                reduce=False,
                include_docs=False
            ).all()
        ]
        for app_id in app_ids:
            app = Application.get(app_id)
            if "vectorlink" in app.domain:
                continue

            if isinstance(app, LinkedApplication):
                yield app

    def handle(self, *args, **options):
        for app in self._iter_linked_apps():
            app.uses_master_form_ids = True
            app.save()
