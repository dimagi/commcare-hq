from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.xform import XForm, parse_xml
from couchforms.models import XFormInstance
from dimagi.utils.couch.database import iter_docs
from django.core.management.base import BaseCommand
from optparse import make_option


class Command(BaseCommand):
    help = 'fix all of the things'

    option_list = BaseCommand.option_list + (
        make_option(
            '--dry-run',
            action='store_true',
            dest='dry_run',
            default=False,
            help="Don't do the actual modifications, just print what would be affected"
        ),
    )

    def handle(self, *args, **options):

        dry_run = options.get("dry_run", True)
        new_xmlnss = {}

        for xform_instance in get_submissions_without_xmlns():
            if xform_instance.app_id in new_xmlnss:
                set_xmlns_on_submission(xform_instance, new_xmlnss[xform_instance.app_id], dry_run)
            else:
                app = Application.get(xform_instance.app_id)
                forms_without_xmlns = get_forms_without_xmlns(app)
                if len(forms_without_xmlns) == 1:
                    new_xmlns = generate_random_xmlns()
                    new_xmlnss[xform_instance.app_id] = new_xmlns
                    set_xmlns_on_form(forms_without_xmlns[0], new_xmlns, dry_run)
                    set_xmlns_on_submission(xform_instance, new_xmlnss[xform_instance.app_id], dry_run)
                else:
                    # This will require more advanced logic
                    pass


def get_submissions_without_xmlns():
    # TODO: This view won't get archived forms etc
    submission_ids = XFormInstance.get_db().view(
        'couchforms/by_xmlns',
        key="undefined",  # TODO: Is this the right key?
        include_docs=False
    ).all()
    return iter_docs(XFormInstance.get_db(), submission_ids)
    # Myabe all_forms/_view/view is better view to use?


def set_xmlns_on_submission(xform_instance, xmlns, dry_run):
    """
    Set the xmlns on an XFormInstance, and the save the document.
    """
    xform_instance.xmlns = xmlns
    xform_instance.form['@xmlns'] = xmlns
    # TODO: Modify the form.xml attachment
    if not dry_run:
        xform_instance.save()


def set_xmlns_on_form(form, xmlns, dry_run):
    """
    Set the xmlns on an app_manager.models.Form, and save the document.
    """
    xml = form.source
    wrapped_xml = XForm(xml)

    data = wrapped_xml.data_node.render()
    # TODO: Possible values for the first arg:
    #   "undefined"
    #   None
    #   "http://www.w3.org/2002/xforms"
    data = data.replace("undefined", xmlns, 1)
    wrapped_xml.instance_node.remove(wrapped_xml.data_node.xml)
    wrapped_xml.instance_node.append(parse_xml(data))
    new_xml = wrapped_xml.render()

    form.source = new_xml
    if not dry_run:
        form.save()


def get_forms_without_xmlns(app):
    # TODO
    raise NotImplementedError

def generate_random_xmlns():
    # TODO
    raise NotImplementedError
