import logging
from lxml import etree as ET

from django.core.management import BaseCommand

from corehq.apps.app_manager.models import Application, PreloadAction
from corehq.apps.app_manager.util import save_xform
from corehq.apps.app_manager.xform import XForm


logger = logging.getLogger('app_migration')
logger.setLevel('DEBUG')


class Command(BaseCommand):
    help = "Migrate an app from case management in the app builder to form builder"

    def handle(self, *args, **options):
        app_id = args[0]
        self.options = options
        logger.info('migrating app {}'.format(app_id))
        self.migrate_app(app_id)
        logger.info('done with migrate_app_to_cmitfb')

    def migrate_app(self, app_id):
        app = Application.get(app_id)
        modules = [m for m in app.modules if m.module_type == 'basic']

        for module in modules:
            forms = [f for f in module.forms if f.doc_type == 'Form']
            for form in forms:
                preload = form.actions.case_preload.preload
                if preload:
                    xform = XForm(form.source)
                    xform.add_case_preloads(preload)
                    save_xform(app, form, ET.tostring(xform.xml))
                    form.actions.load_from_form = form.actions.case_preload
                    form.actions.case_preload = PreloadAction()

        app.vellum_case_management = True
        app.save()
