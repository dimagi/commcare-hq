import json
import os
from copy import deepcopy

from django.core.files.uploadedfile import UploadedFile
from django.core.management.base import BaseCommand

from corehq.apps.hqadmin.management.commands.export_domain_forms_raw import FormMetadata
from corehq.apps.receiverwrapper.auth import AuthContext
from corehq.apps.receiverwrapper.util import submit_form_locally
from couchforms.models import DefaultAuthContext
from io import open


class Command(BaseCommand):
    help = "Sumbit all forms saved by the ``export_domain_forms_raw`` command." \
           "Note that if the domain you are importing into is not the same domain you" \
           "exported from then there will be some inconsistencies since the new domain" \
           "won't have the same user ID's or Application / App Build ID's"

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('folder_path')

    def handle(self, domain, folder_path, **options):
        if not os.path.exists(folder_path):
            raise Exception('Folder path must be the path to a directory')

        for name in os.listdir(folder_path):
            form_dir = os.path.join(folder_path, name)
            if not os.path.isdir(form_dir):
                continue

            with open(os.path.join(form_dir, 'metadata.json'), 'r', encoding='utf-8') as meta:
                metadata = FormMetadata.wrap(json.load(meta))

            form_path = os.path.join(form_dir, 'form.xml')
            if not os.path.exists(form_path) and os.path.isfile(form_path):
                self.stderr.write('{} missing'.format(form_path))
                continue

            attachments_dict = {}
            for name in metadata.attachments:
                path = os.path.join(form_dir, name)
                if os.path.exists(path):
                    file = open(path, 'rb')
                    attachments_dict[name] = UploadedFile(file, name)
                else:
                    self.stderr.write('WARN: missing attachment: {}'.format(path))

            with open(form_path, 'r', encoding='utf-8') as form:
                xml_data = form.read()

            auth_type = metadata.auth_context.get('doc_type', None)
            if auth_type == 'AuthContext':
                auth_context = AuthContext.wrap(deepcopy(metadata.to_json()['auth_context']))
                auth_context.domain = domain
            else:
                auth_context = DefaultAuthContext()

            result = submit_form_locally(
                xml_data,
                domain,
                attachments=attachments_dict,
                received_on=metadata.received_on,
                auth_context=auth_context,
                app_id=metadata.app_id,
                build_id=metadata.build_id
            )
            if not result.response.status_code == 201:
                self.stderr.write(str(result.response))
