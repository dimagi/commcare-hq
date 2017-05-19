import logging
from collections import defaultdict
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
        parser.add_argument('--fix-user-properties', action='store_true',
            help='Fix bad user property references.')
        parser.add_argument('--force', action='store_true',
            help='Migrate even if app.vellum_case_management is already true.')

    def handle(self, **options):
        app_ids_by_domain = defaultdict(set)
        self.force = options["force"]
        self.fix_user_props = options["fix_user_properties"]
        self.migrate_usercase = options["usercase"]
        if not self.fix_user_props:
            raise Exception(
                "This is currently broken and needs to be fixed. "
                "Problems:\n"
                "1. wrong xpath used for user property references\n"
                "2. case references in form.case_references.load are overwritten\n"
                "3. log detaileds about what changed in case of problems.\n"
            )
        for ident in options["app_id_or_domain"]:
            if not (self.migrate_usercase or self.fix_user_props):
                try:
                    app = Application.get(ident)
                    app_ids_by_domain[app.domain].add(ident)
                    continue
                except ResourceNotFound:
                    pass
            app_ids_by_domain[ident].update(get_app_ids_in_domain(ident))

        for domain, app_ids in sorted(app_ids_by_domain.items()):
            logger.info('migrating %s: %s apps', domain, len(app_ids))
            migrated = False
            for app_id in app_ids:
                try:
                    if self.fix_user_props:
                        self.fix_user_properties(app_id)
                    else:
                        migrated = self.migrate_app(app_id)
                    if migrated:
                        logger.info('migrated app %s', app_id)
                except Exception:
                    logger.exception("skipping app %s", app_id)
            if self.migrate_usercase and not USER_PROPERTY_EASY_REFS.enabled(domain):
                USER_PROPERTY_EASY_REFS.set(domain, True, NAMESPACE_DOMAIN)
                logger.info("enabled USER_PROPERTY_EASY_REFS for domain: %s", domain)

        logger.info('done with migrate_app_to_cmitfb')

    def migrate_app(self, app_id):
        app = Application.get(app_id)
        migrate_usercase = should_migrate_usercase(app, self.migrate_usercase)
        if self.migrate_usercase and not migrate_usercase:
            return False
        if app.vellum_case_management and not migrate_usercase and not self.force:
            logger.info('already migrated app {}'.format(app_id))
            return False

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
        return True

    def fix_user_properties(self, app_id):
        app = Application.get(app_id)
        updated = warn = False
        modules = [m for m in enumerate(app.modules) if m[1].module_type == 'basic']
        for modi, module in modules:
            forms = [f for f in enumerate(module.forms) if f[1].doc_type == 'Form']
            for formi, form in forms:
                if not (form.case_references and form.case_references.load):
                    continue
                form_updated, ref_warn = fix_user_props(app, form, modi, formi)
                updated = form_updated or updated
                warn = ref_warn or warn
        if updated:
            app.save()
            logger.info("saved app %s", app_id)
        elif warn:
            logger.warning('app %s not updated', app_id)


USERPROP_PREFIX = (
    "instance('casedb')/casedb/case[@case_type='commcare-user']"
    "[hq_user_id=instance('commcaresession')/session/context/userid]/"
)
BAD_USERCASE_PATH = (
    "instance('casedb')/casedb/case[@case_id=instance('commcaresession')/session/data/case_id]/"
)


def fix_user_props(app, form, modi, formi):
    updated = False
    xform = XForm(form.source)
    refs = {xform.resolve_path(ref): vals
        for ref, vals in form.case_references.load.iteritems()
        if any(v.startswith("#user/") for v in vals)}
    ref_warnings = []
    for node in xform.model_node.findall("{f}setvalue"):
        if (node.attrib.get('ref') in refs
                and node.attrib.get('event') == "xforms-ready"):
            ref = node.attrib.get('ref')
            ref_values = refs[ref]
            if len(ref_values) != 1:
                ref_warnings.append((ref, ref_values))
                continue
            value = (node.attrib.get('value') or "").replace(" ", "")
            userprop = ref_values[0]
            assert userprop.startswith("#user/"), (ref, userprop)
            prop = userprop[len("#user/"):]
            if value == BAD_USERCASE_PATH + prop:
                logger.info("%s/%s setvalue %s -> %s", modi, formi, userprop, ref)
                node.attrib["value"] = USERPROP_PREFIX + prop
                updated = True
            elif value != (USERPROP_PREFIX + prop).replace(" ", ""):
                ref_warnings.append((ref, ref_values))
    if updated:
        save_xform(app, form, ET.tostring(xform.xml))
    if ref_warnings:
        for ref, ref_values in ref_warnings:
            logger.warning("%s/%s %s has unexpected #user refs: %s",
                modi, formi, ref, " ".join(ref_values))
    return updated, ref_warnings


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
