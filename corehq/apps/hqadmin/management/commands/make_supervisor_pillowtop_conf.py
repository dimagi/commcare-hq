import os
from django.conf import settings
import yaml
from corehq.apps.hqadmin.management.commands.make_supervisor_conf import SupervisorConfCommand


class Command(SupervisorConfCommand):
    help = "Make pillowtop supervisord conf - multiple configs per the PILLOWTOPS setting"
    args = ""


    @staticmethod
    def get_pillows_from_settings(self, pillowtops, reject_types=[]):
        """
        Reduce the number of pillows started if there are certain types passed in to reject
        """
        return [pillow for group_key, items in pillowtops.items() for pillow in items if
                group_key not in reject_types]

    def render_configuration_file(self, conf_template_string):
        """
        Hacky override to make pillowtop config. Multiple configs within the conf file
        """
        environment = self.params['environment']
        code_root = self.params['code_root']

        if environment in ['staging']:
            with open(os.path.join(code_root, "scripts", "staging_pillows.yaml"), 'r') as f:
                yml = yaml.load(f)
                reject = yml['pillowtop_blacklist']

        configs = []
        all_pillows = self.get_pillows_from_settings(self, settings.PILLOWTOPS, reject)
        for full_name in all_pillows:
            pillow_name = full_name.split('.')[-1]
            pillow_params = {
                'pillow_name': pillow_name,
                'pillow_option': ' --pillow-name %s' % pillow_name
            }
            pillow_params.update(self.params)
            pillow_rendering = conf_template_string % pillow_params
            configs.append(pillow_rendering)
        return '\n\n'.join(configs)
