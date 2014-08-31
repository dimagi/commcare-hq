from django.core.management.base import BaseCommand, CommandError
from corehq.apps.app_manager.models import Form
from corehq.apps.reports.formdetails.readable import FormQuestion


class Command(BaseCommand):
    help = 'Does things'

    def handle(self, *args, **options):
        self.stdout.write('ran command')

        conf = {
            "form_id": '548fe79579be510fba8fcf49b098a07a49305e2b',
            # List of question ids
            "questions": ['CHW1_transportation_assessment_getting_to_appointments'],
            "additional_properties": []
        }

        # Hmmm... questions might need to be in the form:
        # "questions": [
        #   {
        #       "id": "CHW1_transportation_cm_cityride_activities",
        #        "options": [
        #           {"value": "help_complete_application", "hidden value": "Help patient complete Metro reduced fare pass for disability application"}
        #        ]
        #   }
        # ]
        # This means:
        #   - Create hiddenvalues/subcase spawning for each option of question "CHW1_transportation_cm_cityride_activities"
        #   - For each option in options:
        #       - Instead of having the corresponding hidden value have the default value, it should have a special value

        form = Form.get_form(conf["form_id"])

        # Get the questions specified
        question_dict = {q["value"]:FormQuestion.wrap(q) for q in form.get_questions(["en"])}
        question_ids = {"/data/" + q for q in conf["questions"]}.intersection(question_dict.keys())
        questions = [question_dict[k] for k in question_ids]

        for question in questions:
            print question
            # Create new hidden values for each question option if they don't already exist:
            for option in options:
                #TODO: Check if it exists
                hidden_value_id = None
                hidden_value_text = option.label

                # ex: CHW1_transportation_cm_metro_reduced_activities-help_complete_application
                #     "Help patient complete Metro reduced fare pass for disability application"