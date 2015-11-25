from django.dispatch.dispatcher import Signal

from corehq.apps.domain.models import Domain
from corehq.apps.app_manager.const import CAREPLAN_GOAL, CAREPLAN_TASK
from corehq.apps.app_manager.models import CareplanModule, CareplanConfig, CareplanAppProperties


def create_app_structure_repeat_records(sender, application, **kwargs):
    from corehq.apps.repeaters.models import AppStructureRepeater
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


app_post_save = Signal(providing_args=['application'])

app_post_save.connect(create_app_structure_repeat_records)
app_post_save.connect(update_project_careplan_config)

app_post_release = Signal(providing_args=['application'])
app_post_release.connect(update_project_careplan_config_release)
