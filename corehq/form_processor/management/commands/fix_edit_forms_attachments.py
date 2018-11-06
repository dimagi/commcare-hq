from __future__ import absolute_import
from __future__ import unicode_literals
from __future__ import print_function

from django.core.management.base import BaseCommand
from collections import defaultdict

from corehq.sql_db.util import get_db_aliases_for_partitioned_query
from corehq.form_processor.models import XFormOperationSQL
from corehq.form_processor.backends.sql.dbaccessors import FormAccessorSQL
from corehq.util.log import with_progress_bar


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--source', help='sql/couch')
        parser.add_argument('--update', action='store_true', help='actually update')

    @staticmethod
    def _find_sql_forms_with_missing_attachments():
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
    def _add_attachment_to_form(attachment_id, form_id):
        pass

    def handle(self, **options):
        source = options.get("source") or 'sql'
        perform_update = options.get('update')
        if source == 'sql':
            print('looking for sql forms with missing attachments now')
            forms_to_process = self._find_sql_forms_with_missing_attachments()
        else:
            raise NotImplementedError('finish your work first')
        if perform_update:
            print('starting with adding attachments. Need to update %s forms.' % len(forms_to_process))
            for form_id, attachments in with_progress_bar(list(forms_to_process.items())):
                for attachment_id, original_form_id in attachments:
                    self._add_attachment_to_form(attachment_id, form_id)
