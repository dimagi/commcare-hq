from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
import xmltodict
from django.core.management.base import BaseCommand
from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from xml.etree import ElementTree as ET
import xml


class Command(BaseCommand):
    help = "Scrubs the username from all forms associated with the given user"

    def add_arguments(self, parser):
        parser.add_argument('user_id')
        parser.add_argument('domain')

    def handle(self, user_id, domain, **options):
        this_form_accessor = FormAccessors(domain=domain)
        form_ids = this_form_accessor.get_form_ids_for_user(user_id)
        new_username = "Redacted User (GDPR)"
        for form_data in this_form_accessor.iter_forms(form_ids):
            form_attachment_xml_new = self.parse_form_data(form_data, new_username)
            this_form_accessor.modify_attachment_xml_and_metadata(form_data, form_attachment_xml_new)

    @staticmethod
    def parse_form_data(form_data, new_username):
        # Get the xml attachment from the form data
        form_attachment_xml = form_data.get_attachment("form.xml")

        print("FORM ATTACHMENT BEFORE: {}".format(form_attachment_xml))
        print("============")

        tree = ET.fromstring(form_attachment_xml)
        ET.register_namespace("n0", "http://openrosa.org/jr/xforms")
        ET.register_namespace("n1", "http://commcarehq.org/xforms")
        ET.register_namespace("", "http://openrosa.org/formdesigner/form-processor")

        namespaces = {"n0": "http://openrosa.org/jr/xforms",
                      "n1": "http://commcarehq.org/xforms",
                      "": "http://openrosa.org/formdesigner/form-processor"}
        tree.find("n0:meta", namespaces).find("n0:username", namespaces).text = new_username
        form_attachment_xml = ET.tostring(tree)

        return form_attachment_xml
