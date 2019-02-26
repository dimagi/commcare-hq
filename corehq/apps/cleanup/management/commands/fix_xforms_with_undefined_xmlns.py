from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
import re
from datetime import datetime
from itertools import chain

import six
from couchdbkit import ResourceNotFound

from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.util import get_correct_app_class
from corehq.apps.cleanup.management.commands.fix_forms_and_apps_with_missing_xmlns import \
    name_matches
from corehq.apps.es import FormES
from corehq.apps.es.filters import NOT, doc_type
from corehq.util.couch import IterDB
from corehq.util.quickcache import quickcache
from couchforms.const import ATTACHMENT_NAME
from couchforms.models import XFormInstance
from dimagi.utils.couch.database import iter_docs
from django.core.management.base import BaseCommand
from six.moves import input
from io import open


ONE_HOUR = 60 * 60
INFO = "info"
ERROR = "error"
WARNING = "warning"

SET_XMLNS = "set-xmlns-on-xfrom"
ERROR_SAVING = "error-saving-xform"
MULTI_MATCH = "multiple-possible-forms"
FORM_HAS_UNDEFINED_XMLNS = "build-has-form-with-undefined-xmlns"
CANT_MATCH = "cant-match-xform-to-form"


class Command(BaseCommand):
    help = ("Running this command will fix xform submissions with 'undefined' xmlns."
     " It will only fix xforms that are submitted against builds that have"
     " already been repaired.")

    def add_arguments(self, parser):
        parser.add_argument('log_path')
        parser.add_argument(
            '--dry-run',
            action='store_true',
            dest='dry_run',
            default=False,
            help="Don't do the actual modifications, but still log what would be affected",
        )
        parser.add_argument(
            '--noinput',
            action='store_true',
            dest='noinput',
            default=False,
            help="Run the command without interactive input",
        )

    def handle(self, log_path, **options):

        dry_run = options.get("dry_run", True)
        noinput = options.get("noinput", False)
        log_path = log_path.strip()

        if not noinput and not dry_run:
            confirm = input(
                """
                Are you sure you want to fix XFormInstances with "undefined" xmlns?
                This is NOT a dry run. y/N?
                """
            )
            if confirm != "y":
                print("\n\t\tSwap duplicates cancelled.")
                return

        with open(log_path, "w") as log_file:
            self.fix_xforms(log_file, dry_run)

    @staticmethod
    def fix_xforms(log_file, dry_run):
        unfixable_builds = set()
        total, submissions = get_submissions_without_xmlns()
        xform_db = IterDB(XFormInstance.get_db())
        with xform_db as xform_db:
            for i, xform_instance in enumerate(submissions):
                Command._print_progress(i, total)
                try:
                    xmlns = get_correct_xmlns(xform_instance)
                except MultiplePreviouslyFixedForms as e:
                    if xform_instance.build_id not in unfixable_builds:
                        unfixable_builds.add(xform_instance.build_id)
                        print(six.text_type(e))
                    _log(log_file, WARNING, MULTI_MATCH, xform_instance)
                    continue
                except CantMatchAForm as e:
                    _log(log_file, WARNING, CANT_MATCH, xform_instance)
                    continue
                except BuildHasFormsWithUndefinedXmlns as e:
                    _log(log_file, WARNING, FORM_HAS_UNDEFINED_XMLNS, xform_instance)
                    continue

                if xmlns:
                    set_xmlns_on_submission(
                        xform_instance,
                        xmlns,
                        xform_db,
                        log_file,
                        dry_run,
                    )

        for error_id in xform_db.error_ids:
            _log(ERROR, ERROR_SAVING, xform_id=error_id)

    @staticmethod
    def _print_progress(i, total_submissions):
        if i % 200 == 0 and i != 0:
            print("Progress: {} of {} ({})  {}".format(
                i, total_submissions, round(i / float(total_submissions), 2), datetime.now()
            ))


def _log(stream, level, event, xform=None, xform_id=None):
    basic_template = "[{level}] {event}, xform_id={xform_id}"
    full_template = basic_template + ", domain={xform.domain}, username={xform.metadata.username}, " \
                                     "app_id={xform.app_id}, build_id={xform.build_id}, " \
                                     "xmlns={xform.xmlns}"
    if xform_id:
        msg = basic_template.format(level=level, event=event, xform_id=xform_id)
    else:
        msg = full_template.format(level=level, event=event, xform_id=xform._id, xform=xform)
    stream.write(msg + "\n")


def parse_log_message(line):
    match = re.match(r'^\[(.*)\] ([^,]*), (.*)', line)
    level, event, extras = match.groups()
    extras_dict = {}
    for pair in extras.split(", "):
        key, val = pair.split("=", 1)
        extras_dict[key] = val
    return level, event, extras_dict


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
    old_xml = xform_instance.get_xml().decode('utf-8')
    assert old_xml.count('xmlns="undefined"') == 1
    new_xml = old_xml.replace('xmlns="undefined"', 'xmlns="{}"'.format(xmlns))
    if not dry_run:
        replace_xml(xform_instance, new_xml)

    xform_instance.xmlns = xmlns
    xform_instance.form['@xmlns'] = xmlns
    xform_instance.form_migrated_from_undefined_xmlns = datetime.utcnow()
    if not dry_run:
        xform_db.save(xform_instance)
    _log(log_file, INFO, SET_XMLNS, xform_instance)


def get_forms_without_xmlns(app):
    return [form for form in app.get_forms() if form.xmlns == "undefined"]


def get_previously_fixed_forms(app):
    ret = []
    for form in app.get_forms():
        try:
            if form.form_migrated_from_undefined_xmlns:
                ret.append(form)
        except AttributeError:
            pass
    return ret


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


class MultiplePreviouslyFixedForms(Exception):
    def __init__(self, build_id, app_id):
        template = "Unable to determine matching form. Multiple forms in app " \
                   "{} were previously repaired. Build submitted against was {}"
        super(MultiplePreviouslyFixedForms, self).__init__(template.format(app_id, build_id))


class CantMatchAForm(Exception):
    pass


class BuildHasFormsWithUndefinedXmlns(Exception):
    pass


@quickcache(["xform_instance.build_id"], memoize_timeout=ONE_HOUR)
def get_correct_xmlns(xform_instance):
    if xform_instance.build_id is None:
        return None
    build = get_app(xform_instance.domain, xform_instance.build_id)
    # TODO: What if the app has been deleted?

    previously_fixed_forms_in_build = get_previously_fixed_forms(build)
    if len(previously_fixed_forms_in_build) == 1:
        return previously_fixed_forms_in_build[0].xmlns
    elif len(previously_fixed_forms_in_build) == 0:
        if get_forms_without_xmlns(build):
            # We don't expect this to ever happen
            raise BuildHasFormsWithUndefinedXmlns()
        else:
            matching_forms = find_matching_forms_by_name(xform_instance, build)
            if len(matching_forms) == 1:
                return matching_forms[0].xmlns
            else:
                raise CantMatchAForm()
    else:
        raise MultiplePreviouslyFixedForms(xform_instance.build_id, xform_instance.app_id)


def find_matching_forms_by_name(xform_instance, build):
    return [form for form in build.get_forms() if name_matches(xform_instance.name, form.name)]
