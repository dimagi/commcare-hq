from __future__ import absolute_import
from builtins import range
from django.conf import settings
from corehq.apps.hqadmin.management.commands.make_supervisor_conf import SupervisorConfCommand
from corehq.apps.hqadmin.pillow_settings import get_pillows_for_env


class Command(SupervisorConfCommand):
    help = "Make pillowtop supervisord conf - multiple configs per the PILLOWTOPS setting"

    def render_configuration_file(self, conf_template_string, params):
        """
        Hacky override to make pillowtop config. Multiple configs within the conf file
        """
        pillow_env_configs = params['pillow_env_configs']

        configs = []
        all_pillows = get_pillows_for_env(pillow_env_configs, settings.PILLOWTOPS)
        for pillow_config in all_pillows:
            pillow_name = pillow_config.name
            num_processes = pillow_config.params.get('num_processes', 1)
            pillow_params = {
                'pillow_name': pillow_name,
                'pillow_option': ' --pillow-name %s' % pillow_name,
                'num_processes': num_processes
            }
            pillow_params.update(params)
            for process_number in range(num_processes):
                pillow_params.update({'process_num': process_number})
                pillow_rendering = super(Command, self).render_configuration_file(conf_template_string, pillow_params)
                configs.append(pillow_rendering)
        return '\n\n'.join(configs)
