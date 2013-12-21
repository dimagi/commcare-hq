from datetime import timedelta

from django.dispatch.dispatcher import Signal

from corehq import Domain
from corehq.apps.app_manager.const import CAREPLAN_GOAL, CAREPLAN_TASK
from corehq.apps.domain.models import CareplanAppProperties
from receiver.signals import successful_form_received, Certainty, ReceiverResult
from receiver.xml import ResponseNature
from receiver import xml

from corehq.middleware import OPENROSA_ACCEPT_LANGUAGE
from corehq.apps.app_manager.models import Application, get_app, CareplanModule
from corehq.apps.app_manager.success_message import SuccessMessage


def get_custom_response_message(sender, xform, **kwargs):
    """
    This signal sends a custom response to xform submissions. 
    If the domain has one.
    """
    if xform.metadata and xform.metadata.userID:
        userID = xform.metadata.userID
        xmlns = xform.form.get('@xmlns')
        domain = xform.domain

        try:
            app = get_app(domain, xform.app_id)
        except Exception:
            app = Application.get_by_xmlns(domain, xmlns)

        if app and hasattr(app, 'langs'):
            try:
                lang = xform.openrosa_headers[OPENROSA_ACCEPT_LANGUAGE]
            except (AttributeError, KeyError):
                lang = "default"
            if lang == "default":
                lang = app.build_langs[0] if app.build_langs else None
            message = app.success_message.get(lang)
            if message:
                success_message = SuccessMessage(message, userID, domain=domain, tz=timedelta(hours=0)).render()
                return ReceiverResult(xml.get_simple_response_xml(
                    success_message, nature=ResponseNature.SUBMIT_SUCCESS),
                    Certainty.STRONG)


def create_app_structure_repeat_records(sender, application, **kwargs):
    from corehq.apps.receiverwrapper.models import AppStructureRepeater
    domain = application.domain
    if domain:
        repeaters = AppStructureRepeater.by_domain(domain)
        for repeater in repeaters:
            repeater.register(application)



def update_project_careplan_config(sender, application, **kwargs):
    app_id = application.get_id
    domain = application.domain
    if application.doc_type == 'Application-Deleted':
        if application.has_careplan_module:
            domain = Domain.get_by_name(domain)
            if app_id in domain.careplan_config:
                del domain.careplan_config[app_id]
                domain.save()
    elif application.has_careplan_module:
        for module in application.get_modules():
            if isinstance(module, CareplanModule):
                domain = Domain.get_by_name(domain)
                props = domain.careplan_config.get(app_id, CareplanAppProperties())
                props.name = module.default_name()
                props.case_type = module.case_type
                props.goal_conf = {
                    "edit_module_id": module.id,
                    "edit_form_id": module.get_form_by_type(CAREPLAN_GOAL, 'update').id,
                    "create_module_id": module.id,
                    "create_form_id": module.get_form_by_type(CAREPLAN_GOAL, 'create').id,
                }
                props.task_conf = {
                    "edit_module_id": module.id,
                    "edit_form_id": module.get_form_by_type(CAREPLAN_TASK, 'update').id,
                    "create_module_id": module.id,
                    "create_form_id": module.get_form_by_type(CAREPLAN_TASK, 'create').id,
                }
                domain.careplan_config[app_id] = props
                domain.save()
                break
    else:
        domain = Domain.get_by_name(domain)
        if app_id in domain.careplan_config:
            del domain.careplan_config[app_id]
            domain.save()



successful_form_received.connect(get_custom_response_message)

app_post_save = Signal(providing_args=['application'])

app_post_save.connect(create_app_structure_repeat_records)
app_post_save.connect(update_project_careplan_config)
