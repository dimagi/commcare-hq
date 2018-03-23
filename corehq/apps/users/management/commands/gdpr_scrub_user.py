from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
import xmltodict
from django.core.management.base import BaseCommand
from corehq.form_processor.interfaces.dbaccessors import FormAccessors


class Command(BaseCommand):
    help = "Scrubs the username from all forms associated with the given user"

    def add_arguments(self, parser):
        parser.add_argument('username')
        self.handle("username")

    def handle(self, username, **options):
        DOMAIN = 'test-proj-2'

        # Replace the username in the XML
        this_form_accessor = FormAccessors(domain=DOMAIN)
        form_ids = this_form_accessor.get_form_ids_for_user(user_id)
        for form_data in this_form_accessor.iter_forms(form_ids):

            form_attachment_xml = form_data.get_attachment("form.xml")
            form_attachment_dict = xmltodict.parse(form_attachment_xml)

            # replace the old username with the new username
            form_attachment_dict["data"]["n0:meta"]["n0:username"] = "NEW USERNAME"

            # convert the dict back to xml
            form_attachment_xml_new = xmltodict.unparse(form_attachment_dict)

            # TODO: Save the new xml to the database


        # Replace the username in the form metadata


if __name__=="__main__":
    Command().handle(username="testuser")
