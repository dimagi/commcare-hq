from __future__ import print_function
from __future__ import absolute_import
import json
import os
import sys

from django.core.management.base import BaseCommand
from django.conf import settings
from django.template import Context, Template


class SupervisorConfCommand(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            '--conf_file',
            help='Config template file to use',
            default=False,
        )
        parser.add_argument(
            '--conf_destination',
            help='Rendered supervisor configuration file path destination',
            default=None,
        )
        parser.add_argument(
            '--conf_destination_filename',
            help='(Optional) Rendered supervisor configuration file name; defaults to the value from --conf_file',
            dest='conf_destination_filename',
            default=None,
        )
        parser.add_argument(
            '--params',
            type=str,
            dest='params',
            default=None,
            help='template parameters as JSON data',
        )

    def render_configuration_file(self, conf_template_string, params):
        return Template(conf_template_string).render(Context(params))

    def handle(self, **options):
        self.conf_file_template = options['conf_file']
        self.conf_dest = options['conf_destination']
        self.conf_destination_filename = options['conf_destination_filename'] or self.conf_file_template
        self.params = options['params'] or {}
        if self.params:
            self.params = self.extend_params(json.loads(self.params))

        service_dir = settings.SERVICE_DIR

        conf_template_fullpath = os.path.join(service_dir, self.conf_file_template)
        if not os.path.isfile(conf_template_fullpath):
            sys.exit("[make_supervisor_conf] Error: file %s does not exist as a template to use - you're doing something wrong" % conf_template_fullpath) #needs to be in source control moron!

        if not os.path.exists(self.conf_dest):
            sys.exit("[make_supervisor_confs] Error: the destination path %s is not reachable by this process" % self.conf_dest)

        conf_template_string = None
        with open(conf_template_fullpath, 'r') as fin:
            conf_template_string = fin.read()
        dest_filepath = os.path.join(
            self.conf_dest,
            '%s_%s' % (settings.SERVER_ENVIRONMENT, self.conf_destination_filename)
        )
        rendered_conf = self.render_configuration_file(conf_template_string, self.params)

        self.write_configuration_file(dest_filepath, rendered_conf)

    def write_configuration_file(self, destination_fullpath, rendered_configuration):
        with open(destination_fullpath, 'w') as fout:
            fout.write(rendered_configuration)
            print("\t[make_supervisor_conf] Wrote supervisor configuration: %s" % destination_fullpath)

    def extend_params(self, params):
        import multiprocessing
        cpus = multiprocessing.cpu_count()
        factor = params.get('gunicorn_workers_factor', 1)
        static_factor = params.get('gunicorn_workers_static_factor', 0)
        params['gunicorn_workers'] = static_factor + (factor * cpus)
        return params


class Command(SupervisorConfCommand):
    help = "Make a supervisord conf file to deposit into a services path that supervisord knows about"

