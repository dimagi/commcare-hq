import os
import sys
from optparse import make_option

from django.core.management.base import BaseCommand
from django.conf import settings
from corehq.apps.hqadmin.management.commands import make_supervisor_conf
from corehq.apps.hqadmin.management.commands.make_supervisor_conf import SupervisorConfCommand


class Command(SupervisorConfCommand):
    help = "Make pillowtop supervisord conf - multiple configs per the PILLOWTOPS setting"
    args = ""

    def render_configuration_file(self, conf_template_string):
        """
        Hacky override to make pillowtop config. Multiple configs within the conf file
        """
        configs = []
        for k in settings.PILLOWTOPS.keys():
            pillow_params = {
                'pillow_key': k,
                'pillow_option': ' --pillow-key %s' % k
            }
            pillow_params.update(self.params)
            pillow_rendering = conf_template_string % pillow_params
            configs.append(pillow_rendering)
        return '\n\n'.join(configs)
