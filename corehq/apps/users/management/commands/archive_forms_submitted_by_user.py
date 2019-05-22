from __future__ import absolute_import
from __future__ import unicode_literals
from __future__ import print_function

from io import open
from six.moves import input
from django.core.management.base import BaseCommand

from dimagi.utils.chunked import chunked

from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from corehq.util.log import with_progress_bar


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('user_id')

    def handle(self, domain, user_id, **options):
        form_accessor = FormAccessors(domain)
        form_ids = form_accessor.get_form_ids_for_user(user_id)
        print("Found %s forms for user" % len(form_ids))
        response = input("Are you sure you want to archive them? (yes to proceed)")
        if response == 'yes':
            with open("archived_forms_for_user_%s.txt" % user_id, 'wb') as log:
                for ids in chunked(with_progress_bar(form_ids), 100):
                    ids = list([f for f in ids if f])
                    for form in form_accessor.get_forms(ids):
                        log.write(form.form_id + '\n')
                        form.archive()
