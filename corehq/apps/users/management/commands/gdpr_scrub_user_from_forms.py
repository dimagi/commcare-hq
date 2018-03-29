from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
import xmltodict
from django.core.management.base import BaseCommand
from corehq.form_processor.interfaces.dbaccessors import FormAccessors


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

        # Convert the xml string to dict
        form_attachment_dict = xmltodict.parse(form_attachment_xml)

        # Replace the old username with the new username
        form_attachment_dict["data"]["n0:meta"]["n0:username"] = new_username
        # Convert the dict back to xml
        form_attachment_xml_new = xmltodict.unparse(form_attachment_dict)
        return form_attachment_xml_new
