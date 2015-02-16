import os
import sys
from optparse import make_option

from django.core.management.base import BaseCommand
from django.conf import settings


def parse_files(option, opt, value, parser):
    pairs = value.split('::')
    args_dict = {}
    for p in pairs:
        try:
            k, v = p.split('=', 1)
            args_dict[k] = v
        except ValueError:
            # error handling
            s = p.split('=')
            print "argument error, %s should be key=filepath" % s
            sys.exit()

    setattr(parser.values, option.dest, args_dict)

class SupervisorConfCommand(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('--conf_file', help='Config template file to use', default=False),
        make_option('--conf_destination', help='Rendered supervisor configuration file path destination', default=None),
        make_option('--params',
                    type="string",
                    action='callback',
                    callback=parse_files,
                    dest='params',
                    default={},
                    help='files to upload file1=path1,file2=path2,file3=path3'),
    )

    def render_configuration_file(self, conf_template_string):
        return conf_template_string % self.params


    def handle(self, *args, **options):
        self.conf_file_template = options['conf_file']
        self.conf_dest = options['conf_destination']
        self.params = options['params']

        root_dir = settings.FILEPATH

        conf_template_fullpath = os.path.join(root_dir, 'fab', 'services', 'templates', self.conf_file_template)
        if not os.path.isfile(conf_template_fullpath):
            sys.exit("[make_supervisor_conf] Error: file %s does not exist as a template to use - you're doing something wrong" % conf_template_fullpath) #needs to be in source control moron!

        if not os.path.exists(self.conf_dest):
            sys.exit("[make_supervisor_confs] Error: the destination path %s is not reachable by this process" % self.conf_dest)

        conf_template_string = None
        with open(conf_template_fullpath, 'r') as fin:
            conf_template_string = fin.read()
        dest_filepath = os.path.join(self.conf_dest, '%s_%s' % (settings.SERVER_ENVIRONMENT, self.conf_file_template))
        rendered_conf = self.render_configuration_file(conf_template_string)

        self.write_configuration_file(dest_filepath, rendered_conf)

    def write_configuration_file(self, destination_fullpath, rendered_configuration):
        with open(destination_fullpath, 'w') as fout:
            fout.write(rendered_configuration)
            print "\t[make_supervisor_conf] Wrote supervisor configuration: %s" % destination_fullpath








class Command(SupervisorConfCommand):
    help = "Make a supervisord conf file to deposit into a services path that supervisord knows about"
    args = ""

