import logging
from lxml import etree as ET

from couchdbkit import ResourceNotFound
from django.core.management import BaseCommand

from corehq.apps.app_manager.dbaccessors import get_app_ids_in_domain
from corehq.apps.app_manager.models import Application, PreloadAction, CaseReferences
from corehq.apps.app_manager.util import save_xform
from corehq.apps.app_manager.xform import XForm, SESSION_USERCASE_ID, get_add_case_preloads_case_id_xpath
from corehq.toggles import NAMESPACE_DOMAIN, USER_PROPERTY_EASY_REFS


logger = logging.getLogger('app_migration')
logger.setLevel('DEBUG')


class Command(BaseCommand):
    help = '''
        Migrate apps from case management in the app builder to form builder.
        Pass either domain name(s) (to migrate all apps in the domain) or
        individual app id(s). Will skip any apps that have already been
        migrated.
    '''

    def add_arguments(self, parser):
        parser.add_argument('app_id_or_domain', nargs='+',
            help="App ID or domain name. Must be a domain name "
                 "with --usercase option.")
        parser.add_argument('--usercase', action='store_true',
            help='Migrate user properties.')
        parser.add_argument('--force', action='store_true',
            help='Migrate even if app.vellum_case_management is already true.')

    def handle(self, **options):
        domains = []
        app_ids = []
        self.force = options["force"]
        self.migrate_usercase = options["usercase"]
        for ident in options["app_id_or_domain"]:
            if not self.migrate_usercase:
                try:
                    Application.get(ident)
                    app_ids.append(ident)
                    continue
                except ResourceNotFound:
                    pass
            ids = get_app_ids_in_domain(ident)
            app_ids.extend(ids)
            if ids:
                domains.append(ident)
            logger.info('migrating {} apps in domain {}'.format(len(ids), ident))

        for app_id in app_ids:
            logger.info('migrating app {}'.format(app_id))
            self.migrate_app(app_id)

        if self.migrate_usercase:
            for domain in domains:
                USER_PROPERTY_EASY_REFS.set(domain, True, NAMESPACE_DOMAIN)
            logger.info("enabled USER_PROPERTY_EASY_REFS for domains: %s",
                ", ".join(domains))

        logger.info('done with migrate_app_to_cmitfb')

    def migrate_app(self, app_id):
        app = Application.get(app_id)
        migrate_usercase = should_migrate_usercase(app, self.migrate_usercase)
        if app.vellum_case_management and not migrate_usercase and not self.force:
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
                    migrate_preloads(app, module, form, preloads)

        app.vellum_case_management = True
        app.save()


def migrate_preloads(app, module, form, preloads):
    xform = XForm(form.source)
    case_id_xpath = get_add_case_preloads_case_id_xpath(module, form)
    for kwargs in preloads:
        hashtag = kwargs.pop("hashtag")
        kwargs['case_id_xpath'] = case_id_xpath
        xform.add_case_preloads(**kwargs)
        refs = {path: [hashtag + case_property]
                for path, case_property in kwargs["preloads"].iteritems()}
        if form.case_references:
            form.case_references.load.update(refs)
        else:
            form.case_references = CaseReferences(load=refs)
    save_xform(app, form, ET.tostring(xform.xml))


def should_migrate_usercase(app, migrate_usercase):
    return migrate_usercase and any(form.actions.usercase_preload.preload
        for module in app.modules if module.module_type == 'basic'
        for form in module.forms if form.doc_type == 'Form')
