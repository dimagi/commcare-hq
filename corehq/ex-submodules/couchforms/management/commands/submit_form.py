from django.core.management.base import CommandError, BaseCommand
from optparse import make_option
import os
from dimagi.utils.post import post_data


class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('--method', action='store',
                    dest='method', default='curl',
                    help='Method to upload (curl, pyton), defaults to curl', type='string'),
        make_option('--chunked', action='store_true', dest='use_chunked', default=False,
                    help='Use chunked encoding (default=False)'),
        make_option('--odk', action='store_true', dest='is_odk', default=False,
                    help='Simulate ODK submission (default=False)'),
    )
    help = "Submits a single form to a url with options."
    args = '<filename> <url> [file1 file2 ...]'
    label = "Submit a single form with various options"

    def handle(self, *args, **options):
        if len(args) < 2:
            raise CommandError('Usage is submit_form %s' % self.args)
        file = args[0]
        url = args[1]
        rest = args[2:]
        method = options.get('method', 'curl')
        use_chunked = options.get('use_chunked', False)
        is_odk = options.get('is_odk', False)
        if file is None or url is None:
            raise CommandError('Usage is submit_form %s' % self.args)
        if not os.path.exists(file):
            raise CommandError("File does not exist")

        attachments = []
        for attach_path in rest:
            if not os.path.exists(attach_path):
                raise CommandError("Error, additional file path does not exist: %s" % attach_path)
            else:
                attachments.append((attach_path.replace('.', '_'), attach_path))

        if method == 'curl':
            use_curl = True
        elif method == 'python':
            use_curl = False
        
        print post_data(None, url, path=file, use_curl=use_curl, use_chunked=use_chunked,
                        is_odk=is_odk, attachments=attachments)
