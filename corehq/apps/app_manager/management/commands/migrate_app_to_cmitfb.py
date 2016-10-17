import logging
from lxml import etree as ET

from couchdbkit import ResourceNotFound
from django.core.management import BaseCommand

from corehq.apps.app_manager.dbaccessors import get_app_ids_in_domain
from corehq.apps.app_manager.models import Application, PreloadAction
from corehq.apps.app_manager.util import save_xform
from corehq.apps.app_manager.xform import XForm


logger = logging.getLogger('app_migration')
logger.setLevel('DEBUG')


class Command(BaseCommand):
    args = 'app_id_or_domain'
    help = '''
        Migrate apps from case management in the app builder to form builder.
        Pass either a domain name (to migrate all apps in the domain) or an
        individual app id. Will skip any apps that have already been migrated.
    '''

    def handle(self, *args, **options):
        app_ids = []
        try:
            Application.get(args[0])
            app_ids = [args[0]]
        except ResourceNotFound:
            app_ids = get_app_ids_in_domain(args[0])
            logger.info('migrating {} apps in domain {}'.format(len(app_ids), args[0]))

        for app_id in app_ids:
            logger.info('migrating app {}'.format(app_id))
            self.migrate_app(app_id)

        logger.info('done with migrate_app_to_cmitfb')

    def migrate_app(self, app_id):
        app = Application.get(app_id)
        if app.vellum_case_management:
            logger.info('already migrated app {}'.format(app_id))
            return

        modules = [m for m in app.modules if m.module_type == 'basic']
        for module in modules:
            forms = [f for f in module.forms if f.doc_type == 'Form']
            for form in forms:
                preload = form.actions.case_preload.preload
                if preload:
                    xform = XForm(form.source)
                    xform.add_case_preloads(preload)
                    save_xform(app, form, ET.tostring(xform.xml))
                    form.case_references = {"load": {path: [case_property]
                        for path, case_property in preload.iteritems()}}
                    form.actions.case_preload = PreloadAction()

        app.vellum_case_management = True
        app.save()
