from __future__ import absolute_import
from __future__ import unicode_literals
import logging
from collections import defaultdict
from datetime import datetime
from lxml import etree as ET

from couchdbkit import ResourceNotFound
from django.core.management import BaseCommand

from corehq.apps.app_manager.dbaccessors import get_app, get_app_ids_in_domain
from corehq.apps.app_manager.models import Application, PreloadAction, CaseReferences
from corehq.apps.app_manager.util import save_xform
from corehq.apps.app_manager.xform import (
    XForm, SESSION_USERCASE_ID,
    get_add_case_preloads_case_id_xpath,
    get_case_parent_id_xpath,
)
from dimagi.utils.parsing import json_format_datetime
import six


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
        parser.add_argument('--fix-user-props-caseref', action='store_true',
            help='Fix bad user property references based on form.case_references.')
        parser.add_argument('--force', action='store_true',
            help='Migrate even if app.vellum_case_management is already true.')
        parser.add_argument('-n', '--dry-run', action='store_true', dest='dry_run',
            help='Do not save updated apps, just print log output.')
        parser.add_argument('--fail-hard', action='store_true', dest='fail_hard',
            help='Die when encountering a bad app. Useful when calling via migrate_all_apps_to_cmitfb, '
                 'which only ever passes a single app id.')

    def handle(self, **options):
        app_ids_by_domain = defaultdict(set)
        self.force = options["force"]
        self.dry = "DRY RUN " if options["dry_run"] else ""
        self.fail_hard = options["fail_hard"]
        self.fup_caseref = options["fix_user_props_caseref"]
        self.fix_user_props = options["fix_user_properties"] or self.fup_caseref
        self.migrate_usercase = options["usercase"]
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
            for app_id in app_ids:
                try:
                    app = get_app(domain, app_id)
                    if app.doc_type == "Application":
                        if self.fix_user_props:
                            self.fix_user_properties(app)
                        else:
                            self.migrate_app(app)
                    else:
                        logger.info("Skipping %s/%s because it is a %s", domain, app_id, app.doc_type)
                except Exception as e:
                    logger.exception("skipping app %s/%s", domain, app_id)
                    if self.fail_hard:
                        raise e

        logger.info('done with migrate_app_to_cmitfb %s', self.dry)

    def migrate_app(self, app):
        migrate_usercase = should_migrate_usercase(app, self.migrate_usercase)
        if self.migrate_usercase and not migrate_usercase:
            return False
        if app.vellum_case_management and not migrate_usercase and not self.force:
            logger.info('already migrated app {}'.format(app.id))
            return False
        logger.info('%smigrating app %s/%s', self.dry, app.domain, app.id)

        for module, form, form_ix in iter_forms(app):
            preloads = []
            preload = form.actions.case_preload.preload
            if preload:
                if form.requires == 'case':
                    preloads.append(("#case/", preload))
                form.actions.case_preload = PreloadAction()
            usercase_preload = form.actions.usercase_preload.preload
            if migrate_usercase and usercase_preload:
                preloads.append(("#user/", usercase_preload))
                form.actions.usercase_preload = PreloadAction()
            if preloads:
                migrate_preloads(app, form, preloads, form_ix, self.dry)

        if not self.dry:
            app.vellum_case_management = True
            app.save()
        return True

    def fix_user_properties(self, app):
        updated = False
        if self.fup_caseref:
            # fix user properties based on form.case_references.load
            logger.info("%smigrating %s/%s", self.dry, app.domain, app.id)
            for module, form, form_ix in iter_forms(app):
                if not (form.case_references and form.case_references.load):
                    continue
                updated = fix_user_props_caseref(
                    app, module, form, form_ix, self.dry
                ) or updated
        else:
            # fix user properties based on form.actions.usercase_preload
            # in most recent copy of app before migration
            copy = get_pre_migration_copy(app)
            if copy is None:
                logger.warn("%scopy not found %s/%s version %s",
                    self.dry, app.domain, app.id, app.version)
                return
            logger.info("%smigrating %s/%s: (%s) version diff=%s",
                self.dry, app.domain, app.id, copy.version, app.version - copy.version)
            old_forms = {form.unique_id: form
                for module in copy.modules if module.module_type == 'basic'
                for form in module.forms if form.doc_type == 'Form'}
            for module, new_form, form_ix in iter_forms(app):
                old_form = old_forms.get(new_form.unique_id)
                if old_form is None:
                    logger.warn("form not in pre-migration copy: %s (%s)",
                        form_ix, new_form.unique_id)
                    continue
                preloads = old_form.actions.usercase_preload.preload
                if preloads:
                    updated = fix_user_props_copy(
                        app, module, new_form, form_ix, preloads, self.dry
                    ) or updated
        if updated:
            if not self.dry:
                app.save()
            logger.info("%ssaved app %s", self.dry, app.id)


ORIGINAL_MIGRATION_DATE = datetime(2017, 5, 17, 15, 25)
USERPROP_PREFIX = (
    "instance('casedb')/casedb/case[@case_type='commcare-user']"
    "[hq_user_id=instance('commcaresession')/session/context/userid]/"
)


def iter_forms(app):
    modules = [m for m in enumerate(app.modules) if m[1].module_type == 'basic']
    for modi, module in modules:
        forms = [f for f in enumerate(module.forms) if f[1].doc_type == 'Form']
        for formi, form in forms:
            yield module, form, "%s/%s" % (modi, formi)


def fix_user_props_copy(app, module, form, form_ix, preloads, dry):
    updated = False
    xform = XForm(form.source)
    refs = {xform.resolve_path(ref): prop for ref, prop in six.iteritems(preloads)}
    for node in xform.model_node.findall("{f}setvalue"):
        if (node.attrib.get('ref') in refs
                and node.attrib.get('event') == "xforms-ready"):
            ref = node.attrib.get('ref')
            value = (node.attrib.get('value') or "").replace(" ", "")
            prop = refs[ref]
            userprop = "#user/" + prop
            if value == get_bad_usercase_path(module, form, prop):
                logger.info("%s setvalue %s -> %s", form_ix, userprop, ref)
                node.attrib["value"] = USERPROP_PREFIX + prop
                updated = True
            elif value != USERPROP_PREFIX + prop:
                logger.warn("%s %s has unexpected value: %r (not %s)",
                    form_ix, ref, value, userprop)
    if updated:
        if dry:
            logger.info("updated setvalues in XML:\n%s", "\n".join(line
                for line in ET.tostring(xform.xml).split("\n")
                if "setvalue" in line))
        else:
            save_xform(app, form, ET.tostring(xform.xml))
    return updated


def fix_user_props_caseref(app, module, form, form_ix, dry):
    updated = False
    xform = XForm(form.source)
    refs = {xform.resolve_path(ref): vals
        for ref, vals in six.iteritems(form.case_references.load)
        if any(v.startswith("#user/") for v in vals)}
    ref_warnings = []
    for node in xform.model_node.findall("{f}setvalue"):
        if (node.attrib.get('ref') in refs
                and node.attrib.get('event') == "xforms-ready"):
            ref = node.attrib.get('ref')
            ref_values = refs[ref]
            if len(ref_values) != 1:
                ref_warnings.append((ref, " ".join(ref_values)))
                continue
            value = (node.attrib.get('value') or "").replace(" ", "")
            userprop = ref_values[0]
            assert userprop.startswith("#user/"), (ref, userprop)
            prop = userprop[len("#user/"):]
            if value == get_bad_usercase_path(module, form, prop):
                logger.info("%s setvalue %s -> %s", form_ix, userprop, ref)
                node.attrib["value"] = USERPROP_PREFIX + prop
                updated = True
            elif value != (USERPROP_PREFIX + prop).replace(" ", ""):
                ref_warnings.append((ref, "%r (%s)" % (value, userprop)))
    if updated:
        if dry:
            logger.info("updated setvalues in XML:\n%s", "\n".join(line
                for line in ET.tostring(xform.xml).split("\n")
                if "setvalue" in line))
        else:
            save_xform(app, form, ET.tostring(xform.xml))
    if ref_warnings:
        for ref, ref_values in ref_warnings:
            logger.warning("%s %s has unexpected #user refs: %s",
                form_ix, ref, ref_values)
    return updated


def get_bad_usercase_path(module, form, property_):
    from corehq.apps.app_manager.util import split_path
    case_id_xpath = get_add_case_preloads_case_id_xpath(module, form)
    parent_path, property_ = split_path(property_)
    property_xpath = case_property(property_)
    id_xpath = get_case_parent_id_xpath(parent_path, case_id_xpath=case_id_xpath)
    return id_xpath.case().property(property_xpath)


def case_property(property_):
    return {
        'name': 'case_name',
        'owner_id': '@owner_id'
    }.get(property_, property_)


def get_pre_migration_copy(app):
    from corehq.apps.app_manager.util import get_correct_app_class

    def date_key(doc):
        return doc.get("built_on") or mindate

    mindate = json_format_datetime(datetime(1980, 1, 1))
    migrate_date = json_format_datetime(ORIGINAL_MIGRATION_DATE)
    skip = 0
    docs = None

    while docs is None or date_key(docs[-1]) > migrate_date:
        docs = saved_apps = [row['doc'] for row in Application.get_db().view(
            'app_manager/saved_app',
            startkey=[app.domain, app._id, {}],
            endkey=[app.domain, app._id],
            descending=True,
            skip=skip,
            limit=5,
            include_docs=True,
        )]
        if not docs:
            break
        skip += len(docs)
        docs = sorted(saved_apps, key=date_key, reverse=True)
        for doc in docs:
            if date_key(doc) < migrate_date:
                copy = get_correct_app_class(doc).wrap(doc)
                if copy.version < app.version:
                    return copy
    return None


class SkipApp(Exception):
    pass


def migrate_preloads(app, form, preload_items, form_ix, dry):
    xform = XForm(form.source)
    if form.case_references:
        load_refs = form.case_references.load
    else:
        load_refs = {}
        form.case_references = CaseReferences(load=load_refs)
    for hashtag, preloads in preload_items:
        if hashtag == "#case/":
            xform.add_case_preloads(preloads)
        elif hashtag == "#user/":
            xform.add_casedb()
            for nodeset, prop in preloads.items():
                assert '/' not in prop, (app.id, form.unique_id, prop)
                xform.add_setvalue(ref=nodeset, value=USERPROP_PREFIX + prop)
        else:
            raise ValueError("unknown hashtag: " + hashtag)
        for nodeset, prop in six.iteritems(preloads):
            load_refs.setdefault(nodeset, []).append(hashtag + prop)
            logger.info("%s/%s %s setvalue %s = %s",
                app.domain, app._id, form_ix, nodeset, hashtag + prop)
    if dry:
        logger.info("setvalue XML: %s", " ".join(line.strip()
            for line in ET.tostring(xform.xml).split("\n")
            if "setvalue" in line))
    else:
        save_xform(app, form, ET.tostring(xform.xml))


def should_migrate_usercase(app, migrate_usercase):
    return migrate_usercase and any(form.actions.usercase_preload.preload
        for module in app.modules if module.module_type == 'basic'
        for form in module.forms if form.doc_type == 'Form')
