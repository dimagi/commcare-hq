import logging
import sys
from io import StringIO

from django.core.management.base import BaseCommand

from lxml import etree

from corehq.apps.users.models import CouchUser
from corehq.form_processor.models import XFormInstance

logger = logging.getLogger(__name__)
NEW_USERNAME = "Redacted User (GDPR)"


class Command(BaseCommand):
    help = "Scrubs the username from all forms associated with the given user"

    def add_arguments(self, parser):
        parser.add_argument('username')
        parser.add_argument('domain')

    def handle(self, username, domain, **options):
        user = CouchUser.get_by_username(username)
        if not user:
            logger.info("User {} not found.".format(username))
            sys.exit(1)
        user_id = user._id
        form_ids = XFormInstance.objects.get_form_ids_for_user(domain, user_id)
        input_response = input(
            "Update {} form(s) for user {} in domain {}? (y/n): ".format(len(form_ids), username, domain))
        if input_response == "y":
            for form_data in XFormInstance.objects.iter_forms(form_ids, domain):
                form_attachment_xml_new = self.update_form_data(form_data, NEW_USERNAME)
                XFormInstance.objects.modify_attachment_xml_and_metadata(
                    form_data, form_attachment_xml_new)
            logging.info("Updated {} form(s) for user {} in domain {}".format(len(form_ids), username, domain))
        elif input_response == "n":
            logging.info("No forms updated, exiting.")
        else:
            logging.info("Command not recognized. Exiting.")

    @staticmethod
    def update_form_data(form_data, new_username):
        form_attachment_xml = form_data.get_attachment("form.xml").decode('utf-8')
        xml_elem = etree.parse(StringIO(form_attachment_xml))
        id_elem = xml_elem.find("{http://openrosa.org/jr/xforms}meta").find(
            "{http://openrosa.org/jr/xforms}username")
        id_elem.text = new_username

        new_form_attachment_xml = etree.tostring(xml_elem, encoding='utf-8')

        return new_form_attachment_xml
