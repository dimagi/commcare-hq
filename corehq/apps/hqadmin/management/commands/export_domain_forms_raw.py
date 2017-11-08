from __future__ import absolute_import
import json
import os

import jsonobject
from django.core.management.base import BaseCommand, CommandError

from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from dimagi.ext.jsonobject import JsonObject


class FormMetadata(JsonObject):
    user_id = jsonobject.StringProperty()
    received_on = jsonobject.DateTimeProperty()
    app_id = jsonobject.StringProperty()
    build_id = jsonobject.StringProperty()
    attachments = jsonobject.ListProperty(unicode)
    auth_context = jsonobject.DictProperty()


class Command(BaseCommand):
    help = "Save all form XML documents and attachments for a domain to a folder on disk. " \
           "Use ``import_domain_forms_raw`` to reload the forms into CommCareHQ."

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('folder_path')

    def handle(self, domain, folder_path, **options):
        if os.path.exists(folder_path):
            if not os.path.isdir(folder_path):
                raise CommandError('Folder path must be the path to a directory')
        else:
            os.mkdir(folder_path)

        form_accessors = FormAccessors(domain)
        form_ids = form_accessors.get_all_form_ids_in_domain()
        for form in form_accessors.iter_forms(form_ids):
            form_path = os.path.join(folder_path, form.form_id)
            if not os.path.exists(form_path):
                os.mkdir(form_path)

            form_meta = FormMetadata(
                user_id=form.user_id,
                received_on=form.received_on,
                app_id=form.app_id,
                build_id=form.build_id,
                attachments=form.attachments.keys(),
                auth_context=form.auth_context,
            )

            with open(os.path.join(form_path, 'metadata.json'), 'w') as meta:
                json.dump(form_meta.to_json(), meta)

            xml = form.get_xml()
            with open(os.path.join(form_path, 'form.xml'), 'w') as f:
                f.write(xml)

            for name, meta in form.attachments.items():
                with open(os.path.join(form_path, name), 'w') as f:
                    f.write(form.get_attachment(name))
