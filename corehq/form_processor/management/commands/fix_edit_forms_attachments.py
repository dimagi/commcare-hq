from __future__ import absolute_import
from __future__ import unicode_literals
from __future__ import print_function

from django.core.management.base import BaseCommand
from collections import defaultdict

from io import open
import csv342 as csv

from corehq.sql_db.util import get_db_aliases_for_partitioned_query
from couchforms.models import XFormDeprecated
from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from corehq.form_processor.exceptions import XFormNotFound
from corehq.form_processor.models import XFormOperationSQL
from corehq.form_processor.backends.sql.dbaccessors import FormAccessorSQL
from corehq.form_processor.backends.couch.dbaccessors import FormAccessorCouch
from corehq.util.log import with_progress_bar


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--source', help='sql/couch')
        parser.add_argument('--update', action='store_true', help='actually update')
        parser.add_argument('--inspect', action='store_true', help='just write findings to file')

    @staticmethod
    def _find_sql_forms_with_missing_attachments():
        """
        find all forms that are a result of a form edition
        find the deprecated form and then compare attachments between them
        :return:
        """
        add_forms_with_attachments = defaultdict(list)
        form_accessor = FormAccessorSQL()
        for db_alias in get_db_aliases_for_partitioned_query():
            print('scanning %s' % db_alias)
            edit_form_ids = (XFormOperationSQL.objects.using(db_alias)
                             .filter(operation='edit')
                             .values_list('form_id', flat=True))
            for edit_form_id in with_progress_bar(edit_form_ids):
                edited_form = form_accessor.get_form(edit_form_id)
                deprecated_form_id = edited_form.deprecated_form_id
                original_attachments = list(FormAccessorSQL.get_attachments_for_forms([deprecated_form_id]))
                new_attachments = list(FormAccessorSQL.get_attachments_for_forms([edit_form_id]))
                new_attachment_names = [a.name for a in new_attachments]
                for attachment in original_attachments:
                    if attachment.name not in new_attachment_names:
                        assert attachment.form_id == deprecated_form_id
                        add_forms_with_attachments[edit_form_id].append(
                            (attachment.attachment_id, deprecated_form_id)
                        )
        return add_forms_with_attachments

    @staticmethod
    def _find_couch_forms_with_missing_attachments():
        """
        find deprecated form ids,
        then look for the new form and compare attachments between them
        :return:
        """
        add_forms_with_attachments = defaultdict(list)
        deprecated_form_ids = [
            f['id'] for f in XFormDeprecated.view(
                'all_docs/by_doc_type', startkey=['XFormDeprecated'], endkey=['XFormDeprecated', {}],
                include_docs=False, reduce=False).all()]
        for deprecated_form_id in deprecated_form_ids:
            deprecated_form = XFormDeprecated.get(deprecated_form_id)
            form_accessor = FormAccessors(deprecated_form.domain)
            if deprecated_form.orig_id:
                try:
                    new_form = form_accessor.get_form(deprecated_form.orig_id)
                except XFormNotFound:
                    # fall back to other DB couch/sql to look for the form
                    if form_accessor.db_accessor == FormAccessorSQL:
                        new_form = FormAccessorCouch.get_form(deprecated_form.orig_id)
                    else:
                        new_form = FormAccessorSQL.get_form(deprecated_form_id)
                except ValueError as e:
                    # always is illegal doc id error
                    # https://github.com/dimagi/commcare-hq/blob/652089eb7b63e3967d674580cab55522b5327a22/corehq/blobs/mixin.py#L614
                    print(e)
                    continue
                original_attachments = deprecated_form.attachments
                new_attachments = new_form.attachments
                new_attachment_names = new_attachments.keys()
                for attachment_name in original_attachments:
                    if attachment_name not in new_attachment_names:
                        add_forms_with_attachments[deprecated_form.orig_id].append(
                            (original_attachments[attachment_name]['key'], deprecated_form_id)
                        )
        return add_forms_with_attachments

    @staticmethod
    def _add_attachment_to_form(attachment_id, form_id):
        pass

    def handle(self, **options):
        source = options.get("source") or 'sql'
        if source == 'sql':
            print('looking for sql forms with missing attachments now')
            forms_to_process = self._find_sql_forms_with_missing_attachments()
        elif source == 'couch':
            print('looking for couch forms with missing attachments now')
            forms_to_process = self._find_couch_forms_with_missing_attachments()
        else:
            raise NotImplementedError()
        if options.get('update'):
            print('starting with adding attachments. Need to update %s forms.' % len(forms_to_process))
            for form_id, attachments in with_progress_bar(list(forms_to_process.items())):
                for attachment_id, original_form_id in attachments:
                    self._add_attachment_to_form(attachment_id, form_id)
        elif options.get('inspect'):
            file_name = '%s_forms_missing_attachments.csv' % source
            print('writing findings to file %s' % file_name)
            with open(file_name, 'w') as output_file:
                writer = csv.writer(output_file)
                for form_id in forms_to_process:
                    attachments = forms_to_process[form_id]
                    for attachment_path, source_form_id in attachments:
                        writer.writerow([form_id, source_form_id, attachment_path])