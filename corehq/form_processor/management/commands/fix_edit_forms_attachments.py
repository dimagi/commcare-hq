from __future__ import absolute_import
from __future__ import unicode_literals
from __future__ import print_function

from django.core.management.base import BaseCommand, CommandError
from collections import defaultdict
import datetime

from io import open
import csv342 as csv

from corehq.sql_db.util import get_db_aliases_for_partitioned_query
from corehq.form_processor.exceptions import XFormNotFound
from corehq.form_processor.models import XFormOperationSQL
from corehq.form_processor.backends.sql.dbaccessors import FormAccessorSQL
from corehq.form_processor.backends.couch.dbaccessors import FormAccessorCouch
from corehq.util.log import with_progress_bar
from corehq.blobs import CODES, get_blob_db

EDIT_FORM_FEATURE_LIVE_DATE = datetime.datetime(2018, 5, 14)  # actually 15th
IGNORE_DOMAIN = ['qa-performance-testing']


def get_sql_previous_versions(form_id, form_accessor, index=0, orig_form_id=None):
    """
    :param form_id: edited form id
    :return: all previous versions of a form including itself with the earliest being on top
    """
    orig_form_id = orig_form_id or form_id
    try:
        form_ = form_accessor.get_form(form_id)
    except XFormNotFound:
        try:
            FormAccessorCouch.get_form(form_id)
        except XFormNotFound:
            print('missing form with id %s, looked everywhere. Orig form id %s' % (
                form_id, orig_form_id
            ))
        else:
            print('This form history eventually went into couch, kept till sql. %s' % orig_form_id)
        return []
    if form_.deprecated_form_id:
        index = index + 1
        if index > 100:
            if form_.domain not in IGNORE_DOMAIN:
                print("too high index for form %s. Hence kept just till 10" % orig_form_id)
            return [form_]
        return get_sql_previous_versions(form_.deprecated_form_id, form_accessor, index, orig_form_id) + [form_]
    else:
        return [form_]


class Command(BaseCommand):
    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)
        self.forms = {}
        self.search_after_feature_release = False

    def add_arguments(self, parser):
        parser.add_argument('--source', help='sql/couch')
        parser.add_argument('--update', action='store_true', help='actually update')
        parser.add_argument('--inspect', action='store_true', help='just write findings to file')
        parser.add_argument('--after', action='store_true',
                            help='search for edits after edit form feature release')

    def _find_sql_forms_with_missing_attachments(self):
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
                             .values_list('form_id', flat=True).order_by('-date').distinct())
            for edit_form_id in with_progress_bar(edit_form_ids):
                if edit_form_id in self.forms:
                    # this form was already covered by some other form in its hierarchy
                    continue
                edit_chain = get_sql_previous_versions(edit_form_id, form_accessor)
                original_form = edit_chain[0]
                original_attachments = list(FormAccessorSQL.get_attachments_for_forms([original_form.form_id]))
                for edited_form in edit_chain[1:]:
                    attachments = list(FormAccessorSQL.get_attachments_for_forms([edited_form.form_id]))
                    attachment_names = [a.name for a in attachments]
                    for attachment in original_attachments:
                        if attachment.name != 'form.xml' and attachment.name not in attachment_names:
                            assert attachment.form_id == original_form.form_id
                            self.forms[edited_form.form_id] = edited_form
                            for attachment_to_be_added in add_forms_with_attachments[edited_form.form_id]:
                                if attachment_to_be_added.attachment_id == attachment.attachment_id:
                                    # this attachment add request is already present
                                    continue
                            add_forms_with_attachments[edited_form.form_id].append(attachment)
        return add_forms_with_attachments

    def _find_couch_forms_with_missing_attachments(self):
        """
        find deprecated form ids,
        then look for the new form and compare attachments between them
        :return:
        """
        raise NotImplementedError

    @staticmethod
    def _add_attachment_to_couch_form(attachment_id, form_id):
        raise NotImplementedError

    @staticmethod
    def _add_attachment_to_sql_form(form_id, attachment):
        code = CODES.form_xml if attachment.name == "form.xml" else CODES.form_attachment
        with attachment.read_content(stream=True) as content:
            get_blob_db().put(
                content,
                domain=attachment.form.domain,  # ToDo: Check that this is available on all forms
                parent_id=form_id,
                type_code=code,
                name=attachment.name,
                content_type=attachment.content_type,
                properties=attachment.properties,
            )

    def handle(self, **options):
        self.search_after_feature_release = options.get('after')
        if options.get('inspect') and options.get('update'):
            raise CommandError("Cant have updating with inspect")
        source = options.get("source") or 'sql'
        if source == 'sql':
            print('looking for sql forms with missing attachments now')
            forms_to_process = self._find_sql_forms_with_missing_attachments()
            if options.get('update'):
                print('starting with adding attachments. Need to update %s forms.' % len(forms_to_process))
                for form_id, attachments in with_progress_bar(list(forms_to_process.items())):
                    for attachment in attachments:
                        self._add_attachment_to_sql_form(form_id, attachment)
        elif source == 'couch':
            print('looking for couch forms with missing attachments now')
            forms_to_process = self._find_couch_forms_with_missing_attachments()
        else:
            raise NotImplementedError()
        if options.get('inspect'):
            file_name = '%s_forms_missing_attachments.csv' % source
            print('writing findings to file %s' % file_name)
            with open(file_name, 'w') as output_file:
                writer = csv.writer(output_file)
                for form_id in forms_to_process:
                    attachments = forms_to_process[form_id]
                    for attachment in attachments:
                        writer.writerow([form_id, attachment.form_id,
                                         attachment.attachment_id, attachment.name])
