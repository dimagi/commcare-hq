import logging
from lxml import etree as ET

from django.core.management import BaseCommand

from corehq.apps.app_manager.models import Application, Form, PreloadAction
from corehq.apps.app_manager.util import save_xform
from corehq.apps.app_manager.xform import XForm


logger = logging.getLogger('app_migration')
logger.setLevel('DEBUG')

class Command(BaseCommand):
    help = "Migrate an app from case management in the app builder to form builder"

    def handle(self, *args, **options):
        app_id = args[0]
        self.options = options
        logger.info('migrating app'.format(app_id))
        self.migrate_app(app_id)
        logger.info('done')

    def migrate_app(self, app_id):
        app = Application.get(app_id)
        modules = [m for m in app.modules if m.module_type == 'basic']
        should_save = False

        for mod_idx, module in enumerate(modules):
            forms = [f for f in module.forms if f.doc_type == 'Form']
            for form_idx, form in enumerate(module.forms):
                preload = form.actions.case_preload.preload
                if preload:
                    f = app.get_form(form.unique_id)
                    xform = XForm(f.source)
                    xform.add_case_preloads(preload)
                    save_xform(app, f, ET.tostring(xform.xml))
                    form.actions.load_from_form = form.actions.case_preload
                    form.actions.case_preload = PreloadAction()

        app.support_cmitfb = True
        app.save()
