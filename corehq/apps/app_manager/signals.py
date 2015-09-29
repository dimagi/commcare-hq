from datetime import timedelta

from django.dispatch.dispatcher import Signal

from corehq.apps.domain.models import Domain
from corehq.apps.app_manager.const import CAREPLAN_GOAL, CAREPLAN_TASK
from couchforms.signals import successful_form_received, Certainty, ReceiverResult
from couchforms.xml import ResponseNature
from couchforms import xml

from corehq.middleware import OPENROSA_ACCEPT_LANGUAGE
from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.models import Application, CareplanModule, CareplanConfig, CareplanAppProperties
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
            except (AttributeError, KeyError, TypeError):
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


def update_careplan_config(config, parent_app_id, application):
        app_props = config.app_configs.get(parent_app_id, CareplanAppProperties())
        app_props.latest_release = application.get_id
        for module in application.get_modules():
            if isinstance(module, CareplanModule):
                app_props.name = module.default_name()
                app_props.case_type = module.case_type
                app_props.goal_conf = {
                    "edit_module_id": module.id,
                    "edit_form_id": module.get_form_by_type(CAREPLAN_GOAL, 'update').id,
                    "create_module_id": module.id,
                    "create_form_id": module.get_form_by_type(CAREPLAN_GOAL, 'create').id,
                }
                app_props.task_conf = {
                    "edit_module_id": module.id,
                    "edit_form_id": module.get_form_by_type(CAREPLAN_TASK, 'update').id,
                    "create_module_id": module.id,
                    "create_form_id": module.get_form_by_type(CAREPLAN_TASK, 'create').id,
                }
                break
        config.app_configs[parent_app_id] = app_props
        config.save()
        domain = Domain.get_by_name(application.domain)
        if not domain.has_careplan:
            domain.has_careplan = True
            domain.save()


def careplan_removed(domain_name, config, app_id):
    if config and app_id in config.app_configs:
        del config.app_configs[app_id]
        config.save()

        if not config.app_configs:
            domain = Domain.get_by_name(domain_name)
            domain.has_careplan = False
            domain.save()


def update_project_careplan_config(sender, application, **kwargs):
    domain_name = application.domain
    config = CareplanConfig.for_domain(domain_name)

    if application.doc_type == 'Application-Deleted':
        if application.has_careplan_module:
            careplan_removed(domain_name, config, application.get_id)


def update_project_careplan_config_release(sender, application, **kwargs):
    domain_name = application.domain
    config = CareplanConfig.for_domain(domain_name)
    parent_app_id = application.copy_of

    latest_app = application.get_latest_app(released_only=True)
    if latest_app and latest_app.is_released and latest_app.has_careplan_module:
        config = config or CareplanConfig(domain=domain_name)
        update_careplan_config(config, parent_app_id, latest_app)
    else:
        careplan_removed(domain_name, config, parent_app_id)


successful_form_received.connect(get_custom_response_message)

app_post_save = Signal(providing_args=['application'])

app_post_save.connect(create_app_structure_repeat_records)
app_post_save.connect(update_project_careplan_config)

app_post_release = Signal(providing_args=['application'])
app_post_release.connect(update_project_careplan_config_release)
