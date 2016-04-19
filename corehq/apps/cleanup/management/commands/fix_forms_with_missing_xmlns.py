import uuid
import re
from collections import defaultdict
from datetime import datetime
from itertools import chain

from couchdbkit import ResourceNotFound

from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.exceptions import FormNotFoundException
from corehq.apps.app_manager.models import Application, Form
from corehq.apps.app_manager.util import get_correct_app_class
from corehq.apps.app_manager.xform import XForm, parse_xml
from corehq.apps.es import FormES, AppES
from corehq.apps.es.filters import NOT, doc_type
from corehq.util.couch import IterDB
from corehq.util.log import with_progress_bar
from corehq.util.quickcache import quickcache
from couchforms.const import ATTACHMENT_NAME
from couchforms.models import XFormInstance
from dimagi.utils.couch.database import iter_docs
from django.core.management.base import BaseCommand
from optparse import make_option


ONE_HOUR = 60 * 60


class Command(BaseCommand):
    help = 'Fix forms with "undefined" xmlns'
    args = '<prev_log_path> <log_path>'

    option_list = BaseCommand.option_list + (
        make_option(
            '--dry-run',
            action='store_true',
            dest='dry_run',
            default=False,
            help="Don't do the actual modifications, but still log what would be affected"
        ),
    )

    def handle(self, *args, **options):

        dry_run = options.get("dry_run", True)
        prev_log_path = args[0].strip()
        log_path = args[1].strip()

        unique_id_to_xmlns_map = {}
        app_to_unique_ids_map = defaultdict(set)

        with open(prev_log_path, "r") as prev_log_file:
            self.rebuild_maps(prev_log_file, unique_id_to_xmlns_map, app_to_unique_ids_map)

        with open(log_path, "w") as log_file:
            self.fix_xforms(unique_id_to_xmlns_map, app_to_unique_ids_map, log_file, dry_run)
            self.fix_apps(unique_id_to_xmlns_map, app_to_unique_ids_map, log_file, dry_run)

    @staticmethod
    def rebuild_maps(prev_log_file, unique_id_to_xmlns_map, app_to_unique_ids_map):
        for line in prev_log_file:
            match = re.match(r"Using xmlns (.*) for form id (.*)", line)
            if match:
                xmlns = match.group(1)
                form_unique_id = match.group(2)
                unique_id_to_xmlns_map[form_unique_id] = xmlns

                try:
                    form = Form.get_form(form_unique_id)
                    app = form.get_app()
                    map_key = (app._id, app.domain)
                except ResourceNotFound:
                    map_key = Command._get_map_key_from_es(form_unique_id)
                app_to_unique_ids_map[map_key].add(form_unique_id)

    @staticmethod
    def _get_map_key_from_es(form_unique_id):
        builds_query = (AppES()
                      .remove_default_filters()
                      .term('modules.forms.unique_id', form_unique_id))
        non_builds_query = builds_query.is_build(False)

        # Try getting the "base" app
        result = non_builds_query.run()
        if result.total == 1:
            app_id = result.hits[0]['_id']
            domain = result.hits[0]['domain']
            return (app_id, domain)

        # Try getting builds
        result = builds_query.run()
        app_ids = set([h['copy_of'] for h in result.hits])
        if len(app_ids) == 1:
            app_id = app_ids.pop()
            return (app_id, result.hits[0]['domain'])

        raise Exception("Couldn't find the form {}".format(form_unique_id))

    @staticmethod
    def fix_xforms(unique_id_to_xmlns_map, app_to_unique_ids_map, log_file, dry_run):
        total, submissions = get_submissions_without_xmlns()
        xform_db = IterDB(XFormInstance.get_db())
        with xform_db as xform_db:
            for i, xform_instance in enumerate(submissions):
                Command._print_progress(i, total)
                try:
                    unique_id = get_form_unique_id(xform_instance)
                except (MultipleFormsMissingXmlns, FormNameMismatch) as e:
                    log_file.write(e.message)
                    print e.message
                    continue

                if unique_id:
                    if unique_id not in unique_id_to_xmlns_map:
                        xmlns = get_xmlns(unique_id, xform_instance.app_id,
                                          xform_instance.domain)
                        log_file.write(
                            "Using xmlns {} for form id {}\n".format(xmlns, unique_id)
                        )
                        unique_id_to_xmlns_map[unique_id] = xmlns

                    set_xmlns_on_submission(
                        xform_instance,
                        unique_id_to_xmlns_map[unique_id],
                        xform_db,
                        log_file,
                        dry_run,
                    )

                    log_file.write(
                        "app_to_unique_ids_map[({}, {})].add({})".format(
                            xform_instance.app_id, xform_instance.domain, unique_id
                        )
                    )
                    app_to_unique_ids_map[
                        (xform_instance.app_id, xform_instance.domain)
                    ].add(unique_id)

        for error_id in xform_db.error_ids:
            log_file.write("Failed to save xform {}\n".format(error_id))

    @staticmethod
    def fix_apps(unique_id_to_xmlns_map, app_to_unique_ids_map, log_file, dry_run):
        app_db = IterDB(Application.get_db())
        with app_db as app_db:
            for (app_id, domain), form_unique_ids in with_progress_bar(app_to_unique_ids_map.items()):
                app = get_app(domain, app_id)
                for build in [app] + get_saved_apps(app):
                    for form_unique_id in form_unique_ids:
                        set_xmlns_on_form(
                            form_unique_id,
                            unique_id_to_xmlns_map[form_unique_id],
                            build,
                            log_file,
                            app_db,
                            dry_run
                        )
        for error_id in app_db.error_ids:
            log_file.write("Failed to save app {}\n".format(error_id))

    @staticmethod
    def _print_progress(i, total_submissions):
        if i % 200 == 0 and i != 0:
            print "Progress: {} of {} ({})  {}".format(
                i, total_submissions, round(i / float(total_submissions), 2), datetime.now()
            )


def get_submissions_without_xmlns():
    submissions = XFormInstance.get_db().view(
        'couchforms/by_xmlns',
        key="undefined",
        include_docs=False,
        reduce=False,
    ).all()
    total_submissions = len(submissions)
    submission_id_generator = (s['id'] for s in submissions)
    submissions_doc_generator = (
        XFormInstance.wrap(i)
        for i in iter_docs(XFormInstance.get_db(), submission_id_generator)
    )

    total_error_submissions, error_submissions_doc_generator = _get_error_submissions_without_xmlns()
    return (
        total_submissions + total_error_submissions,
        chain(submissions_doc_generator, error_submissions_doc_generator)
    )


def _get_error_submissions_without_xmlns():

    query = (FormES()
             .xmlns('undefined')
             .remove_default_filter("is_xform_instance")
             .filter(NOT(doc_type('xforminstance')))
             .source(['_id']))
    result = query.run()
    total_error_submissions = result.total
    error_submissions = (
        XFormInstance.wrap(i)
        for i in iter_docs(XFormInstance.get_db(), (x['_id'] for x in result.hits))
    )
    return total_error_submissions, error_submissions


def set_xmlns_on_submission(xform_instance, xmlns, xform_db, log_file, dry_run):
    """
    Set the xmlns on an XFormInstance, and the save the document.
    """
    old_xml = xform_instance.get_xml()
    assert old_xml.count('xmlns="undefined"') == 1
    new_xml = old_xml.replace('xmlns="undefined"', 'xmlns="{}"'.format(xmlns))
    if not dry_run:
        replace_xml(xform_instance, new_xml)

    xform_instance.xmlns = xmlns
    xform_instance.form['@xmlns'] = xmlns
    xform_instance.form_migrated_from_undefined_xmlns = datetime.utcnow()
    if not dry_run:
        xform_db.save(xform_instance)
    log_file.write(
        "Set new xmlns {} on submission {}\n".format(xmlns, xform_instance._id)
    )


def set_xmlns_on_form(form_id, xmlns, app_build, log_file, app_db, dry_run):
    """
    Set the xmlns on a form and all the corresponding forms in the saved builds
    that are copies of app.
    (form is an app_manager.models.Form)
    """
    try:
        form_in_build = app_build.get_form(form_id)
    except FormNotFoundException:
        return

    if form_in_build.xmlns == "undefined":
        xml = form_in_build.source
        wrapped_xml = XForm(xml)

        data = wrapped_xml.data_node.render()
        data = data.replace("undefined", xmlns, 1)
        wrapped_xml.instance_node.remove(wrapped_xml.data_node.xml)
        wrapped_xml.instance_node.append(parse_xml(data))
        new_xml = wrapped_xml.render()

        form_in_build.source = new_xml
        form_in_build.form_migrated_from_undefined_xmlns = datetime.utcnow()
        log_file.write(
            "New xmlns for form {form_id} in app {app_build._id} is {new_xmlns}\n".format(
                form_id=form_id,
                app_build=app_build,
                new_xmlns=xmlns
            ))
        if not dry_run:
            app_db.save(app_build)


def get_forms_without_xmlns(app):
    return [form for form in app.get_forms() if form.xmlns == "undefined"]


def generate_random_xmlns():
    return 'http://openrosa.org/formdesigner/{}'.format(uuid.uuid4())


def replace_xml(xform, new_xml):
    if (
        xform._attachments and
        ATTACHMENT_NAME in xform._attachments and
        'data' in xform._attachments[ATTACHMENT_NAME]
    ):
        raise Exception("Unexpected attachment format: _attachments")

    else:
        try:
            xform.put_attachment(new_xml, name=ATTACHMENT_NAME, content_type='text/xml')
        except ResourceNotFound:
            raise Exception("Unexpected attachment format: old attachment scheme")


def get_saved_apps(app):
    saved_apps = Application.get_db().view(
        'app_manager/saved_app',
        startkey=[app.domain, app._id],
        endkey=[app.domain, app._id, {}],
        include_docs=True,
    )
    return [get_correct_app_class(row['doc']).wrap(row['doc']) for row in saved_apps]


class MultipleFormsMissingXmlns(Exception):
    def __init__(self, build_id):
        msg = "Multiple forms missing xmlns for build {}".format(
            build_id
        )
        super(MultipleFormsMissingXmlns, self).__init__(msg)


class FormNameMismatch(Exception):
    def __init__(self, instance_id, instance_build_id, form_unique_id):
        msg = "xform {} name does not match form {} name in build {}".format(
            instance_id,
            form_unique_id,
            instance_build_id
        )
        super(FormNameMismatch, self).__init__(msg)


@quickcache(["xform_instance.build_id"], memoize_timeout=ONE_HOUR)
def get_form_unique_id(xform_instance):
    if xform_instance.build_id is None:
        return None
    app = get_app(xform_instance.domain, xform_instance.build_id)
    # TODO: What if the app has been deleted?
    forms_without_xmlns = get_forms_without_xmlns(app)
    if len(forms_without_xmlns) != 1:
        raise MultipleFormsMissingXmlns(xform_instance.build_id)
    form = forms_without_xmlns[0]
    if not _name_matches(xform_instance.name, form.name):
        raise FormNameMismatch(
            xform_instance._id,
            xform_instance.build_id,
            form.unique_id,
        )
    return form.unique_id


def get_xmlns(form_unique_id, app_id, domain):
    app = get_app(domain, app_id)
    existing_xmlns = set()
    for build in [app] + get_saved_apps(app):
        try:
            form = build.get_form(form_unique_id)
        except FormNotFoundException:
            continue
        if form.xmlns != "undefined":
            existing_xmlns.add(form.xmlns)
    if len(existing_xmlns) == 1:
        return existing_xmlns.pop()
    assert len(existing_xmlns) == 0
    return generate_random_xmlns()


def _name_matches(xform_name, form_names):
    if xform_name in form_names.values():
        return True
    if xform_name in [u"{} [{}]".format(v, k) for k, v in form_names.iteritems()]:
        return True
    return False
