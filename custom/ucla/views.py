from __future__ import absolute_import
from __future__ import unicode_literals
from lxml import etree

from django.urls import reverse
from django.http import HttpResponse

from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.decorators import require_deploy_apps
from corehq.apps.app_manager.schemas.document.form_action import (
    FormActionCondition,
)
from corehq.apps.app_manager.models import (
    OpenSubCaseAction,
)
from corehq.apps.app_manager.util import save_xform
from corehq.apps.app_manager.xform import namespaces, _make_elem
from corehq.apps.app_manager.app_schemas.app_case_metadata import (
    FormQuestion
)
from custom.ucla.forms import TaskCreationForm


@require_deploy_apps
def task_creation(request, domain, app_id, module_id, form_id):
    '''
    This view is meant to be a run as a one-off script to support a specific
    app that Jeremy is writing. Running this script subsequent times on the
    same form will not have adverse affects.
    :param request:
    :param domain:
    :param app_id:
    :param module_id:
    :param form_id:
    :return:
    '''
    if request.method == 'POST':

        html_form = TaskCreationForm(request.POST)
        if html_form.is_valid():

            questions = html_form.cleaned_data['question_ids'].split()
            form = get_app(domain, app_id).modules[int(module_id)].forms[int(form_id)]
            # Make changes to the form
            message = _ucla_form_modifier(form, questions)
            return HttpResponse(message, content_type="text/plain")

        return HttpResponse("Soemthing was wrong with the form you submitted. Your CommCare form is unchanged.", content_type="text/plain")

    elif request.method == 'GET':
        html_form = TaskCreationForm()
        response = HttpResponse()
        response.write('<form action="'+reverse('ucla_task_creation', args=(domain, app_id, module_id, form_id))+'" method="post">')
        response.write(html_form.as_p())
        response.write('<p><input type="submit" value="Process Form"></p>')
        response.write("</form>")
        return response
    else:
        return HttpResponse("GET or POST only.", content_type="text/plain")


def _ucla_form_modifier(form, question_ids):

    message = ""

    xform = form.wrapped_xform()

    # Get the questions specified in question_ids
    question_dict = {q["value"].split("/")[-1]: FormQuestion.wrap(q) for q in form.get_questions(["en"])}
    question_ids = {q for q in question_ids}.intersection(list(question_dict.keys()))
    questions = [question_dict[k] for k in question_ids]

    # Get the existing subcases
    existing_subcases = {c.case_name:c for c in form.actions.subcases}

    message += "Found %s questions.\n" % len(questions)

    for question in questions:
        for option in question.options:

            hidden_value_tag = question.value.split("/")[-1] + "-" + option.value
            hidden_value_path = "/data/" + hidden_value_tag
            hidden_value_text = option.label

            # Create new hidden values for each question option if they don't already exist:

            if hidden_value_tag not in question_dict:

                # Add data element
                tag = "{x}%s" % hidden_value_tag
                element = etree.Element(tag.format(**namespaces))
                xform.data_node.append(element)

                # Add bind
                xform.itext_node.addprevious(_make_elem("bind", {
                    "nodeset": xform.resolve_path(hidden_value_path),
                    "calculate": '"'+hidden_value_text+'"'
                }))

                message += "Node " + hidden_value_path + " created!\n"
            else:
                message += "Node " + hidden_value_path + " already exists, skipping.\n"

            # Create FormActions for opening subcases

            if hidden_value_path not in existing_subcases:
                action = OpenSubCaseAction(
                    condition=FormActionCondition(
                        type='if',
                        question=question.value,
                        operator='selected',
                        answer=option.value,
                    ),
                    case_name=hidden_value_path,
                    case_type='task',
                    # Note, the case properties will not necessarily be created in the order given.
                    case_properties={
                        'task_responsible': '/data/task_responsible',
                        'task_due': '/data/task_due',
                        'owner_id': '/data/owner_id',
                        'task_risk_factor': '/data/task_risk_factor',
                        'study_id': '/data/study_id',
                        'patient_name': '/data/patient_name'
                    },
                    close_condition=FormActionCondition(
                        answer=None,
                        operator=None,
                        question=None,
                        type='never'
                    )
                )
                form.actions.subcases.append(action)
                message += "OpenSubCaseAction " + hidden_value_path + " created!\n"
            else:
                message += "OpenSubCaseAction " + hidden_value_path + " already exists, skipping.\n"

    app = form.get_app()
    # Save the xform modifications
    save_xform(app, form, etree.tostring(xform.xml, encoding="unicode"))
    # save the action modifications
    app.save()
    message += "Form saved.\n"
    return message
