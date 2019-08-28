import json
from copy import deepcopy


def _get_pillow_configs_from_settings_dict(pillows_by_group):
    # this sucks, but not sure there's a better way to make it available to fabric
    from manage import init_hq_python_path
    init_hq_python_path()
    from pillowtop.utils import get_pillow_configs_from_settings_dict
    return get_pillow_configs_from_settings_dict(pillows_by_group)


def get_pillows_for_env(pillow_env_configs, pillows_by_group=None):
    """
    :param pillow_env_configs {pillow_name: {params to pass to supervisor generator}}
    """
    if pillows_by_group is None:
        from django.conf import settings
        pillows_by_group = settings.PILLOWTOPS
    return _get_pillows_for_env(pillow_env_configs, pillows_by_group)


def _get_pillows_for_env(pillow_env_configs, pillows_by_group):
    ret = []
    pillow_names = set(pillow_env_configs)
    pillow_configs = _get_pillow_configs_from_settings_dict(pillows_by_group)
    pillows_for_env = [config for config in pillow_configs if config.name in pillow_names]
    for config in pillows_for_env:
        final_config = deepcopy(config)
        final_config.params.update(pillow_env_configs[config.name])
        ret.append(final_config)

    return ret


def test_pillow_settings(env_name, pillows_by_group):
    from fab.fabfile import load_env
    from fab.utils import get_pillow_env_config
    load_env(env_name)
    pillows = get_pillows_for_env(get_pillow_env_config(env_name), pillows_by_group=pillows_by_group)

    print("Configured Pillows")
    print(json.dumps(pillows, sort_keys=True, indent=2))
