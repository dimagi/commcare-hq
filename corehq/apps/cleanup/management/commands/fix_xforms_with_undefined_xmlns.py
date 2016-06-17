import uuid
import re
from collections import defaultdict
from datetime import datetime
from itertools import chain

from couchdbkit import ResourceNotFound

from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.exceptions import FormNotFoundException
from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.util import get_correct_app_class
from corehq.apps.app_manager.xform import XForm, parse_xml
from corehq.apps.es import FormES
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


def xmlns_map_log_message(xmlns, unique_id):
    return "Using xmlns {} for form id {}\n".format(xmlns, unique_id)



class Command(BaseCommand):
    help = ("Running this command will fix xform submissions with 'undefined' xmlns."
     " It will only fix xforms that are submitted against builds that have"
     " already been repaired.")

    args = '<log_path>'

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
        log_path = args[0].strip()

        with open(log_path, "w") as log_file:
            self.fix_xforms(log_file, dry_run)

    @staticmethod
    def fix_xforms(log_file, dry_run):
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
                        log_file.write(xmlns_map_log_message(xmlns, unique_id))
                        unique_id_to_xmlns_map[unique_id] = xmlns

                    set_xmlns_on_submission(
                        xform_instance,
                        unique_id_to_xmlns_map[unique_id],
                        xform_db,
                        log_file,
                        dry_run,
                    )

                    key = (xform_instance.app_id, xform_instance.domain)
                    val = unique_id
                    if val not in app_to_unique_ids_map[key]:
                        log_file.write(unique_ids_map_log_message(key[0], key[1], unique_id))
                        app_to_unique_ids_map[key].add(val)

        for error_id in xform_db.error_ids:
            log_file.write("Failed to save xform {}\n".format(error_id))

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


def get_forms_without_xmlns(app):
    return [form for form in app.get_forms() if form.xmlns == "undefined"]




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
