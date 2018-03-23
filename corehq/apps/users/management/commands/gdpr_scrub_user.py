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
        user_id = "0a286c0eb864a382a85974336f9dad09"
        this_form_accessor = FormAccessors(domain=DOMAIN)
        form_ids = this_form_accessor.get_form_ids_for_user(user_id)
        new_username = "Deleted username success"
        for form_data in this_form_accessor.iter_forms(form_ids):
            self.replace_username_in_xml(form_data, new_username)
            self.replace_username_in_metadata()




    def replace_username_in_xml(self, form_data, new_username):
        form_attachment_xml = form_data.get_attachment("form.xml")
        form_attachment_dict = xmltodict.parse(form_attachment_xml)

        # replace the old username with the new username
        form_attachment_dict["data"]["n0:meta"]["n0:username"] = new_username

        # convert the dict back to xml
        form_attachment_xml_new = xmltodict.unparse(form_attachment_dict)

        # TODO: Save the new xml to the database

    def replace_username_in_metadata(self):
        pass


if __name__=="__main__":
    Command().handle(username="testuser")
