from django.core.management.base import BaseCommand

from dimagi.utils.chunked import chunked

from corehq.form_processor.models import XFormInstance
from corehq.util.log import with_progress_bar


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('user_id')

    def handle(self, domain, user_id, **options):
        get_forms = XFormInstance.objects.get_forms
        form_ids = XFormInstance.objects.get_form_ids_for_user(domain, user_id)
        print("Found %s forms for user" % len(form_ids))
        response = input("Are you sure you want to archive them? (yes to proceed)")
        if response == 'yes':
            with open("archived_forms_for_user_%s.txt" % user_id, 'wb') as log:
                for ids in chunked(with_progress_bar(form_ids), 100):
                    ids = list([f for f in ids if f])
                    for form in get_forms(ids, domain):
                        log.write(form.form_id + '\n')
                        form.archive()
