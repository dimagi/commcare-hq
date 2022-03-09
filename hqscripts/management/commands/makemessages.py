from django.core.management.commands import makemessages


class Command(makemessages.Command):
    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument('--no-fuzzy', action='store_true', help='Remove fuzzy strings.')

    def handle(self, *args, **options):
        no_fuzzy = options['no_fuzzy']
        if no_fuzzy:
            # The underlying parser only passes custom msgattrib_options if '--no-obsolete' is true,
            # so we have to do a bit of hacking here
            no_obsolete = options['no_obsolete']
            if no_obsolete:
                # If we are removing obsolete messages already, just add in removing fuzzy messages
                self.msgattrib_options += ['--no-fuzzy']
            else:
                # Otherwise, we need to fake obsolete messages while only actually removing fuzzy messages
                options['no_obsolete'] = True
                self.msgattrib_options = ['--no-fuzzy']

        super().handle(*args, **options)
