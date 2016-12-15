import logging
from lxml import etree as ET

from couchdbkit import ResourceNotFound
from django.core.management import BaseCommand

from corehq.apps.app_manager.dbaccessors import get_app_ids_in_domain
from corehq.apps.app_manager.models import Application, PreloadAction
from corehq.apps.app_manager.util import save_xform
from corehq.apps.app_manager.xform import XForm, SESSION_USERCASE_ID


logger = logging.getLogger('app_migration')
logger.setLevel('DEBUG')


class Command(BaseCommand):
    args = 'app_id_or_domain'
    help = '''
        Migrate apps from case management in the app builder to form builder.
        Pass either a domain name (to migrate all apps in the domain) or an
        individual app id. Will skip any apps that have already been migrated.
    '''
    option_list = (
        make_option('--usercase',
                    action='store_true',
                    help='Migrate user properties'),
    )

    def handle(self, *args, **options):
        app_ids = []
        self.migrate_usercase = options.get("usercase")
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
        migrate_usercase = should_migrate_usercase(app, self.migrate_usercase)
        if app.vellum_case_management and not migrate_usercase:
            logger.info('already migrated app {}'.format(app_id))
            return

        modules = [m for m in app.modules if m.module_type == 'basic']
        for module in modules:
            forms = [f for f in module.forms if f.doc_type == 'Form']
            for form in forms:
                preloads = []
                preload = form.actions.case_preload.preload
                if preload:
                    if form.requires == 'case':
                        preloads.append({
                            "hashtag": "#case/",
                            "preloads": preload,
                        })
                    form.actions.case_preload = PreloadAction()
                usercase_preload = form.actions.usercase_preload.preload
                if migrate_usercase and usercase_preload:
                    preloads.append({
                        "hashtag": "#user/",
                        "preloads": usercase_preload,
                        "case_id_xpath": SESSION_USERCASE_ID,
                    })
                    form.actions.usercase_preload = PreloadAction()
                if preloads:
                    migrate_preloads(app, form, preloads)

        app.vellum_case_management = True
        app.save()


def migrate_preloads(app, form, preloads):
    xform = XForm(form.source)
    for kwargs in preloads:
        hashtag = kwargs.pop("hashtag")
        xform.add_case_preloads(**kwargs)
        refs = {path: [hashtag + case_property]
                for path, case_property in kwargs["preloads"].iteritems()}
        if form.case_references:
            form.case_references["load"].update(refs)
        else:
            form.case_references = {"load": refs}
    save_xform(app, form, ET.tostring(xform.xml))


def should_migrate_usercase(app, migrate_usercase):
    return migrate_usercase and any(form.actions.usercase_preload.preload
        for module in app.modules if module.module_type == 'basic'
        for form in module.forms if form.doc_type == 'Form')
