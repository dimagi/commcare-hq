import os
import sys
from optparse import make_option

from django.core.management.base import BaseCommand
from django.conf import settings
from corehq.apps.hqadmin.management.commands import make_supervisor_conf
from corehq.apps.hqadmin.management.commands.make_supervisor_conf import SupervisorConfCommand


class Command(SupervisorConfCommand):
    help = "Make a supervisord conf file to deposit into a services path that supervisord knows about"
    args = ""

    option_list = BaseCommand.option_list + (
        make_option('--conf_file', help='Config template file to use', default=False),
        make_option('--conf_destination', help='Rendered supervisor configuration file path destination', default=None),
        make_option('--params',
                    type="string",
                    action='callback',
                    callback=make_supervisor_conf.parse_files,
                    dest='params',
                    default={},
                    help='files to upload file1=path1,file2=path2,file3=path3'),
    )

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
