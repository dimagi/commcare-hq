from django.conf import settings
from corehq.apps.hqadmin.management.commands.make_supervisor_conf import SupervisorConfCommand
from fab.pillow_settings import get_pillows_for_env


class Command(SupervisorConfCommand):
    help = "Make pillowtop supervisord conf - multiple configs per the PILLOWTOPS setting"
    args = ""

    def render_configuration_file(self, conf_template_string, params):
        """
        Hacky override to make pillowtop config. Multiple configs within the conf file
        """
        environment = params['environment']

        configs = []
        all_pillows = get_pillows_for_env(environment, settings.PILLOWTOPS)
        for pillow_config in all_pillows:
            pillow_name = pillow_config.name
            pillow_params = {
                'pillow_name': pillow_name,
                'pillow_option': ' --pillow-name %s' % pillow_name
            }
            pillow_params.update(params)
            pillow_rendering = super(Command, self).render_configuration_file(conf_template_string, pillow_params)
            configs.append(pillow_rendering)
        return '\n\n'.join(configs)
