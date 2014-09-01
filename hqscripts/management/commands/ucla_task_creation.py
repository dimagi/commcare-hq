from django.core.management.base import BaseCommand, CommandError
from corehq.apps.app_manager.models import (
    Form,
    FormActionCondition,
    OpenSubCaseAction,
)
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

                # Create new hidden values for each question option if they don't already exist:

                hidden_value_path = question.value + "-" + option.value
                hidden_value_text = option.label

                # ex: /data/CHW1_transportation_cm_metro_reduced_activities-help_complete_application
                #     "Help patient complete Metro reduced fare pass for disability application"

                if hidden_value_path not in question_dict:
                    # TODO: Create a new hidden value

                    # How do I do this?
                    # Idea:
                    # Get the XForm with
                    #   xform = form.wrapped_xform()
                    # Modify the XForm
                    #   (how?)
                    # Save the XForm with
                    #   form.add_stuff_to_xform(xform)

                    # corehq/apps/app_manager/views.py:1397 This might be another route (see save_xform)


                    # Add data element

                    data_node = xform_root[0][1][0][0]
                    ns = "{%s}"%data_node.nsmap[None]
                    tag = hidden_value_path.replace("/data/", "")

                    if data_node.find(ns+tag) == None:
                        data_node.append(etree.Element(ns+tag))
                    else:
                        self.stdout.write("data element " + hidden_value_path + " already exists, skipping.")
                    #print(etree.tostring(xform_root, pretty_print=True))
                    #import ipdb; ipdb.set_trace()

                    # Add bind

                    #itext_node = xform_root.find("{http://www.w3.org/1999/xhtml}head/{http://www.w3.org/2002/xforms}model/{http://www.w3.org/2002/xforms}itext")
                    #itext_node.addprevious()

                    # <bind nodeset="/data/CHW1_transportation_cm_cityride_outside_LA_criteria1-label" calculate="&quot;Determine if patient might qualify for City Ride in other LA County cities under Dial A Ride and faciliate application process.&quot;"/>
                    new_bind = etree.Element(
                        "bind",
                        attrib={
                            'nodeset': hidden_value_path,
                            'calculate': '"'+hidden_value_text+'"',
                        }
                    )



                else:
                    self.stdout.write("Node " + hidden_value_path + " already exists, skipping.")

                # Create FormActions for opening subcases

                # corehq/apps/app_manager/views.py:1540

                if hidden_value_path not in existing_subcases:
                    '''
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
                    '''
                else:
                    self.stdout.write("OpenSubCaseAction " + hidden_value_path + " already exists, skipping.")
        self.stdout.write("Saving modified app...")

        #form.get_app().save()

        self.stdout.write('command finished')