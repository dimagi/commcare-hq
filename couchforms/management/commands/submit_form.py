from django.core.management.base import CommandError, BaseCommand
from optparse import make_option
import os
from dimagi.utils.post import post_data


class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
    #       make_option('--file', action='store', dest='file', default=None, help='File to upload REQUIRED', type='string'),
    #       make_option('--url', action='store', dest='url', default=None, help='URL to upload to*', type='string'),
    make_option('--method', action='store',
                dest='method', default='curl',
                help='Method to upload (curl, pyton), defaults to curl', type='string'),
    make_option('--chunked', action='store_true', dest='use_chunked', default=False,
                help='Use chunked encoding (default=False)'),
    make_option('--odk', action='store_true', dest='is_odk', default=False,
                help='Simulate ODK submission (default=False)'),
    )
    help = "Submits a single form to a url with options."
    args = '[<filename> <url>]'#"[--file <filename> --url <url> [optional --method {curl | python} --chunked --odk]]"
    label = "Submit a single form with various options"

    def handle(self, *args, **options):
        print os.path.abspath(os.path.curdir)
        if len(args) != 2:
            raise CommandError('Usage is submit_form %s' % self.args)
        file = args[0]
        url = args[1]
        method = options.get('method', 'curl')
        use_chunked = options.get('use_chunked', False)
        is_odk = options.get('is_odk', False)
        if file == None or url == None:
            raise CommandError('Usage is submit_form %s' % self.args)
        if not os.path.exists(file):
            raise CommandError("File does not exist")

        if method == 'curl':
            use_curl = True
        elif method == 'python':
            use_curl = False
        
        print post_data(None, url, path=file, use_curl=use_curl, use_chunked=use_chunked, is_odk=is_odk)

