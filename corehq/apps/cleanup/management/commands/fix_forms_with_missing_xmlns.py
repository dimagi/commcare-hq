import uuid
from collections import namedtuple
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
from corehq.apps.es.forms import xmlns
from corehq.util.couch import IterDB
from corehq.util.quickcache import quickcache
from couchforms.const import ATTACHMENT_NAME
from couchforms.models import XFormInstance
from dimagi.utils.couch.database import iter_docs
from django.core.management.base import BaseCommand
from optparse import make_option


ONE_HOUR = 60 * 60


NewXmlnsInfo = namedtuple("NewXmlnsInfo", ["form_names", "xmlns"])


class Command(BaseCommand):
    help = 'Fix forms with "undefined" xmlns'
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

        new_xmlnss = {}
        num_fixed = 0
        total, submissions = get_submissions_without_xmlns()

        with open(log_path, "w") as f:
            xform_db = IterDB(XFormInstance.get_db())
            app_db = IterDB(Application.get_db())
            with xform_db as xform_db:
                with app_db as app_db:
                    for i, xform_instance in enumerate(submissions):
                        self._print_progress(i, total, num_fixed)
                        new_xmls_info = new_xmlnss.get(xform_instance.app_id, None)
                        if new_xmls_info and xform_instance.name in new_xmls_info.form_names:
                            num_fixed += 1
                            # We've already generated a new xmlns for this app
                            set_xmlns_on_submission(
                                xform_instance,
                                new_xmls_info.xmlns,
                                xform_db,
                                f,
                                dry_run,
                            )
                        else:
                            app = get_app(xform_instance.domain, xform_instance.app_id)
                            forms_without_xmlns = get_forms_without_xmlns(app)
                            if len(forms_without_xmlns) == 1:
                                form = forms_without_xmlns[0]
                                if xform_instance.name in form.name.values():
                                    if not xforms_with_real_xmlns_possibly_exist(app._id, form):
                                        num_fixed += 1
                                        new_xmlns = generate_random_xmlns()
                                        new_xmlnss[xform_instance.app_id] = NewXmlnsInfo(form.name.values(), new_xmlns)
                                        set_xmlns_on_form(form, new_xmlns, app, f, app_db, dry_run)
                                        set_xmlns_on_submission(
                                            xform_instance,
                                            new_xmlns,
                                            xform_db,
                                            f,
                                            dry_run,
                                        )
            for error_id in list(xform_db.error_ids) + list(app_db.error_ids):
                f.write("Failed to save {}\n".format(error_id))

    def _print_progress(self, i, total_submissions, num_fixed):
        if i % 500 == 0 and i != 0:
            print "Progress: {} of {} ({})".format(
                i, total_submissions, round(i / float(total_submissions), 2)
            )
            print "We can fix {} of {} ({})".format(
                num_fixed, i, round(num_fixed / float(i), 2)
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


@quickcache(["app_id", "form.unique_id"], memoize_timeout=ONE_HOUR)
def xforms_with_real_xmlns_possibly_exist(app_id, form):
    """
    Return True if there exist xforms submitted to the given app against a form
    with the same name as the given name that have a real xmlns.

    If this is True, it could indicate that the form had an xlmns, had submissions,
    then lost the xmlns. If that's the case, we would want to give the submissions
    this xmlns, not a new random one.
    """
    for form_name in form.name.values():
        query = (FormES()
                 .term('form.@name', form_name)
                 .app(app_id)
                 .filter(NOT(xmlns('undefined')))
                 .remove_default_filter('is_xform_instance'))
        if query.count():
            return True
    return False


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


def set_xmlns_on_form(form, xmlns, app, log_file, app_db, dry_run):
    """
    Set the xmlns on a form and all the corresponding forms in the saved builds
    that are copies of app.
    (form is an app_manager.models.Form)
    """
    form_id = form.unique_id
    for app_build in [app] + get_saved_apps(app):
        try:
            form_in_build = app_build.get_form(form_id)
        except FormNotFoundException:
            continue

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
