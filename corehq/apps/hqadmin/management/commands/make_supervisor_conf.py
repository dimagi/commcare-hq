import os
import socket
from django.core.management import call_command
from django.template.loader import render_to_string
import sys
from dimagi.utils import gitinfo
from django.core.management.base import BaseCommand
from corehq.apps.hqadmin.models import HqDeploy
from datetime import datetime
from optparse import make_option
from django.conf import settings

def parse_files(option, opt, value, parser):
    pairs = value.split(',')
    args_dict = {}
    for p in pairs:
        s = p.split('=')
        if len(s) != 2:
            print "argument error, %s should be key=filepath" % s
            sys.exit()
        k = s[0]
        v = s[1]
        args_dict[k] = v
    setattr(parser.values, option.dest, args_dict)

class Command(BaseCommand):
    help = "Creates an HqDeploy document to record a successful deployment."
    args = "[user]"

    option_list = BaseCommand.option_list + (
        make_option('--conf_file', help='Config file to use', default=False),
        make_option('--conf_destination', help='Supervisor configuration file path destination', default=None),
        make_option('--params',
                    type="string",
                    action='callback',
                    callback=parse_files,
                    dest='params',
                    default={},
                    help='files to upload file1=path1,file2=path2,file3=path3'),
    )
    
    def handle(self, *args, **options):
        conf_dest = options['conf_destination']
        conf_file = options['conf_file']
        root_dir = settings.FILEPATH
        params = options['params']
        environment = settings.SERVER_ENVIRONMENT
        print params

        with open(os.path.join(root_dir, 'services', 'templates', conf_file), 'r') as fin:
            conf_string = fin.read()
            rendered_conf = conf_string % params
            with open(os.path.join(conf_dest, '%s_%s' % (environment, conf_file)), 'w') as fout:
                fout.write(rendered_conf)
            print rendered_conf


