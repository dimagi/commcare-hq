import logging
import os
import jsonobject
import yaml


class _PillowAction(jsonobject.JsonObject):
    _allow_dynamic_properties = False
    include_groups = jsonobject.ListProperty(unicode, exclude_if_none=True)
    exclude_groups = jsonobject.ListProperty(unicode, exclude_if_none=True)
    include_pillows = jsonobject.ListProperty(unicode, exclude_if_none=True)
    exclude_pillows = jsonobject.ListProperty(unicode, exclude_if_none=True)


def apply_pillow_actions_to_pillows(pillow_actions, pillows_by_group):
    return _apply_pillow_actions_to_pillows(map(_PillowAction, pillow_actions),
                                            pillows_by_group)


def _apply_pillow_actions_to_pillows(pillow_actions, pillows_by_group):
    all_pillows_items = pillows_by_group.items()
    selected_pillows = {pillow
                        for _, pillows in all_pillows_items
                        for pillow in pillows}
    for action in pillow_actions:
        for group_key, pillows in all_pillows_items:
            for pillow in pillows:
                if group_key in action.exclude_groups:
                    selected_pillows.remove(pillow)
                if group_key in action.include_groups:
                    selected_pillows.add(pillow)
                if pillow in action.exclude_pillows:
                    selected_pillows.remove(pillow)
                if pillow in action.include_pillows:
                    selected_pillows.add(pillow)
    return selected_pillows


def get_pillow_actions_for_env(env_name, base_path=None):
    pillow_actions = []
    for name in ['default', env_name]:
        pillow_action = get_single_pillow_action(name, base_path)
        if pillow_action:
            pillow_actions.append(pillow_action)
    return pillow_actions


def get_single_pillow_action(env_name, base_path=None):
    """
    pillows_by_group should be something in the format of settings.PILLOWTOPS
    env_name should correspond to fab/pillows/{env_name}.yml (if applicable)

    """
    if base_path is None:
        base_path = os.path.join(os.path.dirname(__file__), 'pillows')

    filename = '{}.yml'.format(env_name)
    file_path = os.path.join(base_path, filename)
    if os.path.isfile(file_path):
        with open(file_path) as f:
            try:
                yml = yaml.load(f)
                pillow_action = _PillowAction.wrap(yml)
            except Exception:
                # just to give the person debugging a path to the file
                logging.error('Error in file {}'.format(file_path))
                raise
            else:
                return pillow_action
    else:
        return None


def get_pillows_for_env(env_name, pillows_by_group=None, base_path=None):
    if pillows_by_group is None:
        from django.conf import settings
        pillows_by_group = settings.PILLOWTOPS
    pillow_actions = get_pillow_actions_for_env(env_name, base_path)
    return _apply_pillow_actions_to_pillows(pillow_actions, pillows_by_group)


def test_pillow_settings(env_name, pillows_by_group, extra_debugging=False):
    def dump_yaml(obj):
        return yaml.safe_dump(obj, default_flow_style=False)

    if extra_debugging:
        print 'Pillow settings overview for {}'.format(env_name)
        print dump_yaml([action.to_json()
                         for action in get_pillow_actions_for_env(env_name)])

    pillows = get_pillows_for_env(env_name, pillows_by_group=pillows_by_group)

    print 'Included Pillows'
    print dump_yaml(sorted(pillows))

    print 'Excluded Pillows'
    print dump_yaml(sorted({pillow for _pillows in pillows_by_group.values()
                            for pillow in _pillows} - pillows))
