from django.core.management import call_command
from statici18n.management.commands import compilejsi18n


class Command(compilejsi18n.Command):

    def add_arguments(self, parser):
        super().add_arguments(parser)

    def handle(self, **options):
        self.stdout.write('Generating JS translations...')
        super().handle(**options)
        self.stdout.write('\nGenerated Chat Widget translations...')
        call_command("generate_widget_translations")
