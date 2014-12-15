import os
from django.conf import settings
import yaml
from corehq.apps.hqadmin.management.commands.make_supervisor_conf import SupervisorConfCommand


class Command(SupervisorConfCommand):
    help = "Make pillowtop supervisord conf - multiple configs per the PILLOWTOPS setting"
    args = ""


    @staticmethod
    def get_pillows_from_settings(pillowtops, yml=None):
        """
        Reduce the number of pillows started if there are certain types passed in to reject
        """
        yml = yml or {}
        reject_types = yml.get('pillowtop_blacklist', [])
        reject_pillows = yml.get('pillow_blacklist', [])

        return [pillow for group_key, items in pillowtops.items() for pillow in items if
                group_key not in reject_types and pillow not in reject_pillows]

    @staticmethod
    def get_rejected_pillow_types(code_root, environment):
        """
        Check if a file exists for this environment, then load the rejected pillow types from that file
        Return: None or []
        """
        fpath = os.path.join(code_root, "scripts", "%s_pillows.yaml" % environment)
        if os.path.isfile(fpath):
            with open(fpath, 'r') as f:
                yml = yaml.load(f)
                return yml

        return {}

    def render_configuration_file(self, conf_template_string):
        """
        Hacky override to make pillowtop config. Multiple configs within the conf file
        """
        environment = self.params['environment']
        code_root = self.params['code_root']

        reject = self.get_rejected_pillow_types(code_root, environment)

        configs = []
        all_pillows = self.get_pillows_from_settings(settings.PILLOWTOPS, reject)
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
