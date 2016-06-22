import jsonobject
import yaml


class _PillowAction(jsonobject.JsonObject):
    _allow_dynamic_properties = False
    include_groups = jsonobject.ListProperty(unicode, exclude_if_none=True)
    exclude_groups = jsonobject.ListProperty(unicode, exclude_if_none=True)
    include_pillows = jsonobject.ListProperty(unicode, exclude_if_none=True)
    exclude_pillows = jsonobject.ListProperty(unicode, exclude_if_none=True)


def apply_pillow_actions_to_pillows(pillow_actions, pillows_by_group):
    def coerce_to_pillow_action(obj):
        if isinstance(obj, _PillowAction):
            return obj
        return _PillowAction(obj)

    return _apply_pillow_actions_to_pillows(map(coerce_to_pillow_action, pillow_actions), pillows_by_group)


def _get_pillow_configs_from_settings_dict(pillows_by_group):
    # this sucks, but not sure there's a better way to make it available to fabric
    from manage import init_hq_python_path
    init_hq_python_path()
    from pillowtop.utils import get_pillow_configs_from_settings_dict
    return get_pillow_configs_from_settings_dict(pillows_by_group)


def _apply_pillow_actions_to_pillows(pillow_actions, pillows_by_group):
    def is_relevant(pillow_actions, pillow_config):

        def _is_a_match(p_config, list_of_pillows):
            return (
                p_config.class_name in list_of_pillows or
                p_config.name in list_of_pillows
            )

        # the default is to include if nothing specified
        relevant = True
        # the order of these checks is important since the actions are resolved in the order they are passed in
        for action in pillow_actions:
            if pillow_config.section in action.include_groups:
                assert pillow_config.section not in action.exclude_groups
                relevant = True
            if pillow_config.section in action.exclude_groups:
                relevant = False
            if _is_a_match(pillow_config, action.include_pillows):
                assert pillow_config.class_name not in action.exclude_pillows
                relevant = True
            if _is_a_match(pillow_config, action.exclude_pillows):
                relevant = False

        return relevant

    return filter(
        lambda p_conf: is_relevant(pillow_actions, p_conf),
        set(_get_pillow_configs_from_settings_dict(pillows_by_group))
    )


def get_pillow_actions_for_env(pillow_env_configs):
    pillow_actions = []
    for config in pillow_env_configs:
        pillow_action = get_single_pillow_action(config)
        if pillow_action:
            pillow_actions.append(pillow_action)
    return pillow_actions


def get_single_pillow_action(pillow_env_config):
    """
    pillows_by_group should be something in the format of settings.PILLOWTOPS
    env_name should correspond to fab/pillows/{env_name}.yml (if applicable)

    """
    return _PillowAction.wrap(pillow_env_config)


def get_pillows_for_env(pillow_env_configs, pillows_by_group=None):
    if pillows_by_group is None:
        from django.conf import settings
        pillows_by_group = settings.PILLOWTOPS
    pillow_actions = get_pillow_actions_for_env(pillow_env_configs)
    return apply_pillow_actions_to_pillows(pillow_actions, pillows_by_group)


def test_pillow_settings(env_name, pillows_by_group, extra_debugging=False):
    def dump_yaml(pillow_configs):
        names = [config.name for config in pillow_configs]
        return yaml.safe_dump(names, default_flow_style=False)

    if extra_debugging:
        print 'Pillow settings overview for {}'.format(env_name)
        print dump_yaml([action.to_json()
                         for action in get_pillow_actions_for_env(env_name)])

    from fab.fabfile import get_pillow_env_config
    pillows = list(get_pillows_for_env([get_pillow_env_config(env_name)], pillows_by_group=pillows_by_group))

    print 'Included Pillows'
    print dump_yaml(sorted(pillows))

    print 'Excluded Pillows'
    pillow_configs = list(_get_pillow_configs_from_settings_dict(pillows_by_group))
    print dump_yaml(sorted(set(pillow_configs) - set(pillows)))
