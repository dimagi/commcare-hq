from django.core.management.base import BaseCommand, CommandError
from corehq.apps.app_manager.models import (
    Form,
    FormActionCondition,
    OpenSubCaseAction,
)
from corehq.apps.app_manager.util import save_xform
from corehq.apps.reports.formdetails.readable import FormQuestion
from lxml import etree


class Command(BaseCommand):
    help = 'Does things'

    def handle(self, *args, **options):
        conf = {
            "form_id": '3ea3d49524fec7c7a2fb1f92f3a6d599048dfa54',  # sandbox
            #"form_id": '548fe79579be510fba8fcf49b098a07a49305e2b', # jeremy copy
            # List of question ids
            "questions": [
                'my-multi-select',
                #'CHW1_transportation_cm_metro_reduced_activities',
                #'CHW1_transportation_assessment_getting_to_appointments',
            ],
            "additional_properties": []
        }

        form = Form.get_form(conf["form_id"])

        source = form.source.encode("utf8", "replace") # Is this ok?
        parser = etree.XMLParser(remove_blank_text=True)
        xform_root = etree.fromstring(source, parser)

        # Get the questions specified in conf
        question_dict = {q["value"]:FormQuestion.wrap(q) for q in form.get_questions(["en"])}
        question_ids = {"/data/" + q for q in conf["questions"]}.intersection(question_dict.keys())
        questions = [question_dict[k] for k in question_ids]

        # Get the existing subcases
        existing_subcases = {c.case_name:c for c in form.actions.subcases}

        for question in questions:
            for option in question.options:

                hidden_value_path = question.value + "_" + option.value
                hidden_value_text = option.label

                # Create new hidden values for each question option if they don't already exist:

                if hidden_value_path not in question_dict:
                    # Add data element
                    data_node = xform_root[0][1][0][0]
                    ns = "{%s}" % data_node.nsmap[None]
                    tag = hidden_value_path.replace("/data/", "")
                    #TODO: Am I supposed to be adding the namespace like this?
                    data_node.append(etree.Element(ns+tag))

                    # Add bind
                    ns = "{%s}" % xform_root.nsmap[None]
                    itext_node = xform_root[0][1].find(ns+"itext")
                    bind_node = etree.Element(ns+"bind")
                    # Setting attributes like this instead of with a dict enforces order
                    bind_node.attrib["nodeset"] = hidden_value_path
                    bind_node.attrib["calculate"] = '"'+hidden_value_text+'"'
                    itext_node.addprevious(bind_node)

                else:
                    self.stdout.write("Node " + hidden_value_path + " already exists, skipping.")

                # Create FormActions for opening subcases

                if hidden_value_path not in existing_subcases:
                    action = OpenSubCaseAction(
                        condition=FormActionCondition(
                            type='if',
                            question=question.value,
                            operator='selected',
                            answer=option.label,
                        ),
                        case_name=hidden_value_path,
                        case_type='task',
                        # TODO: Determine if this puts the case properties in the expected order.
                        case_properties={
                            'task_responsible': '/data/task_responsible',
                            'task_due': '/data/task_due',
                            'owner_id': '/data/owner_id',
                            'task_risk_factor': '/data/task_risk_factor',
                        },
                        close_condition=FormActionCondition(
                            answer=None,
                            operator=None,
                            question=None,
                            type='never'
                        )
                    )
                    form.actions.subcases.append(action)
                else:
                    self.stdout.write("OpenSubCaseAction " + hidden_value_path + " already exists, skipping.")
        self.stdout.write("Saving modified app...")

        app = form.get_app()
        # Save the xform modifications
        # TODO: It is possible that I am not preserving the old indentation style of form.source. Does this matter?
        save_xform(app, form, etree.tostring(xform_root, pretty_print=True))
        # save the action modifications
        app.save()

        print form.source
        self.stdout.write('command finished')