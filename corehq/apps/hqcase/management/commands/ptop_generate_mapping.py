from django.core.management.base import NoArgsCommand, BaseCommand
import sys
from dimagi.utils.modules import to_function

class MappingOutputCommand(BaseCommand):
    help="Generate mapping JSON of our ES indexed types. Generic"
    option_list = NoArgsCommand.option_list + (
        )

    doc_class_str = None
    doc_class = None

    def finish_handle(self):
        raise NotImplemented("Finish this!")

    def handle(self, *args, **options):
        if self.doc_class is None and self.doc_class_str is None:
            #in the case where we want to make this a generic anyclass user
            if len(args) != 1:
                print "\tEnter a doc class!\n"
                sys.exit(1)
            self.doc_class_str = args[0].split('.')[-1]
            self.doc_class = to_function(args[0])
        self.finish_handle()



