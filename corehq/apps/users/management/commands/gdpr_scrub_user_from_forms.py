from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.management.base import BaseCommand
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from StringIO import StringIO
from lxml import etree
import sys
import logging


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Scrubs the username from all forms associated with the given user"

    def add_arguments(self, parser):
        parser.add_argument('username')
        parser.add_argument('domain')

    def handle(self, username, domain, **options):
        this_form_accessor = FormAccessors(domain=domain)
        user = CommCareUser.get_by_username(username)
        if not user:
            logger.info("User {} not found.".format(username))
            sys.exit()
        user_id = user._id
        form_ids = this_form_accessor.get_form_ids_for_user(user_id)
        new_username = "Redacted User (GDPR)"
        forms_updated = 0
        for form_data in this_form_accessor.iter_forms(form_ids):
            form_attachment_xml_new = self.parse_form_data(form_data, new_username)
            this_form_accessor.modify_attachment_xml_and_metadata(form_data, form_attachment_xml_new)
            forms_updated += 1
        logging.info("Updated {} forms for user {}".format(forms_updated, username))


    @staticmethod
    def parse_form_data(form_data, new_username):
        form_attachment_xml = form_data.get_attachment("form.xml")

        xml_elem = etree.parse(StringIO(form_attachment_xml))
        id_elem = xml_elem.find("{http://openrosa.org/jr/xforms}meta").find(
            "{http://openrosa.org/jr/xforms}username")
        id_elem.text = new_username

        new_form_attachment_xml = etree.tostring(xml_elem, pretty_print=True).decode("UTF-8")

        return new_form_attachment_xml
