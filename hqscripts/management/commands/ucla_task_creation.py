from django.core.management.base import BaseCommand, CommandError
from corehq.apps.app_manager.models import FormBase


class Command(BaseCommand):
    help = 'Does things'

    def handle(self, *args, **options):
        self.stdout.write('ran command')

        conf = {
            "form_id": None,
            # List of question ids
            "questions": ['CHW1_transportation_assessment_getting_to_appointments'],
            "additional_properties": []
        }

        form = FormBase.get_form(conf["form_id"])
