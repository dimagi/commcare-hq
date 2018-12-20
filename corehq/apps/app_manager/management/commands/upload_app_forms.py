from __future__ import print_function

from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.management.base import BaseCommand, CommandError

import os
from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.util import save_xform
from datetime import datetime
from corehq.apps.users.models import CouchUser
from corehq.const import SERVER_DATETIME_FORMAT_NO_SEC
from io import open


class Command(BaseCommand):
    help = """
        Uploads a a directory of forms to an app. See also: download_app_forms
    """

    def add_arguments(self, parser):
        parser.add_arguments(
            'path',
        )
        parser.add_arguments(
            'app_id',
        )
        parser.add_arguments(
            '--deploy',
            action='store_true',
            dest='deploy',
            default=False,
            help="Deploy application, by making a new build and starring it.",
        )
        parser.add_arguments(
            '--user',
            action='store',
            dest='user',
            default=None,
            help="Username to use for deployer.",
        )
        parser.add_arguments(
            '--comment',
            action='store',
            dest='comment',
            default=None,
            help="Comment (used for if you deploy the application)",
        )

    def handle(self, path, app_id, **options):
        if options['deploy'] and not options['user']:
            raise CommandError('Deploy argument requires a user')
        elif options['deploy']:
            user = CouchUser.get_by_username(options['user'])
            if not user:
                raise CommandError("Couldn't find user with username {}".format(options['user']))

        app = Application.get(app_id)
        for module_dir in os.listdir(path):
            module_index, name = module_dir.split(' - ')
            module = app.get_module(int(module_index))
            for form_name in os.listdir(os.path.join(path, module_dir)):
                form_index, name = form_name.split(' - ')
                form = module.get_form(int(form_index))
                with open(os.path.join(path, module_dir, form_name), 'rb') as f:
                    save_xform(app, form, f.read())

        app.save()
        print('successfully updated {}'.format(app.name))
        if options['deploy']:
            # make build and star it
            comment = options.get('comment', 'form changes from {0}'.format(datetime.utcnow().strftime(SERVER_DATETIME_FORMAT_NO_SEC)))
            copy = app.make_build(
                comment=comment,
                user_id=user._id,
            )
            copy.is_released = True
            copy.save(increment_version=False)
            print('successfully released new version')
