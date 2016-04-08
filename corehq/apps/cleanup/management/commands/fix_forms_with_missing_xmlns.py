import uuid

from couchdbkit import ResourceNotFound

from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.util import get_correct_app_class
from corehq.apps.app_manager.xform import XForm, parse_xml
from corehq.apps.es import FormES
from corehq.apps.es.filters import NOT
from corehq.apps.es.forms import xmlns
from couchforms.const import ATTACHMENT_NAME
from couchforms.models import XFormInstance
from dimagi.utils.couch.database import iter_docs
from django.core.management.base import BaseCommand
from optparse import make_option


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
            for i, xform_instance in enumerate(submissions):
                if i % 500 == 0 and i != 0:
                    print "Progress: {} of {} ({})".format(i, total, round(i / float(total), 2))
                    print "We can fix {} of {} ({})".format(
                        num_fixed, i, round(num_fixed / float(i), 2)
                    )
                if xform_instance.app_id in new_xmlnss:
                    num_fixed += 1
                    # We've already generated a new xmlns for this app
                    set_xmlns_on_submission(xform_instance, new_xmlnss[xform_instance.app_id], dry_run)
                    f.write("Set new xmlns on submission {}\n".format(xform_instance._id))
                else:
                    app = Application.get(xform_instance.app_id)
                    forms_without_xmlns = get_forms_without_xmlns(app)
                    if len(forms_without_xmlns) == 1:
                        form = forms_without_xmlns[0]
                        if not xforms_with_real_xmlns_possibly_exist(app._id, form):
                            num_fixed += 1
                            new_xmlns = generate_random_xmlns()
                            new_xmlnss[xform_instance.app_id] = new_xmlns
                            f.write("New xmlns for form {form.unique_id} in app {app._id} is {new_xmlns}\n".format(
                                form=form,
                                app=app,
                                new_xmlns=new_xmlns
                            ))
                            set_xmlns_on_form(form, new_xmlns, app, dry_run)
                            set_xmlns_on_submission(xform_instance, new_xmlnss[xform_instance.app_id], dry_run)
                            f.write("Set new xmlns on submission {}\n".format(xform_instance._id))


def get_submissions_without_xmlns():
    # TODO: This view won't get archived forms etc
    submissions = XFormInstance.get_db().view(
        'couchforms/by_xmlns',
        key="undefined",
        include_docs=False,
        reduce=False,
    ).all()
    total_submissions = len(submissions)
    submission_id_generator = (s['id'] for s in submissions)
    doc_generator = (XFormInstance.wrap(i) for i in iter_docs(XFormInstance.get_db(), submission_id_generator))
    return total_submissions, doc_generator


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
                 .filter(NOT(xmlns('undefined'))))
        if query.count():
            return True
    return False


def set_xmlns_on_submission(xform_instance, xmlns, dry_run):
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
    if not dry_run:
        xform_instance.save()


def set_xmlns_on_form(form, xmlns, app, dry_run):
    """
    Set the xmlns on a form and all the corresponding forms in the saved builds
    that are copies of app.
    (form is an app_manager.models.Form)
    """
    form_id = form.unique_id
    for app_build in [app] + get_saved_apps(app):
        form_in_build = app_build.get_form(form_id)

        xml = form_in_build.source
        wrapped_xml = XForm(xml)

        data = wrapped_xml.data_node.render()
        data = data.replace("undefined", xmlns, 1)
        wrapped_xml.instance_node.remove(wrapped_xml.data_node.xml)
        wrapped_xml.instance_node.append(parse_xml(data))
        new_xml = wrapped_xml.render()

        form_in_build.source = new_xml
        if not dry_run:
            app_build.save()


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
