from __future__ import print_function
from django.core.management.base import BaseCommand, CommandError

import os
from corehq.apps.app_manager.models import Application
from corehq.apps.commtrack.util import unicode_slug


class Command(BaseCommand):
    args = '<app_id> <path_to_dir>'
    help = """
        Downloads an app's forms in a more convenient directory structure for working with offline.
        See also: upload_app_forms
    """

    def handle(self, *args, **options):
        # todo: would be nice if this worked off remote servers too
        if len(args) != 2:
            raise CommandError('Usage: %s\n%s' % (self.args, self.help))
        app_id, path = args

        # setup directory
        if not os.path.exists(path):
            os.mkdir(path)

        app = Application.get(app_id)
        for module_index, module in enumerate(app.get_modules()):
            module_dir_name = '{index} - {name}'.format(index=module_index, name=unicode_slug(module.default_name()))
            module_dir = os.path.join(path, module_dir_name)
            if not os.path.exists(module_dir):
                os.mkdir(module_dir)
            for form_index, form in enumerate(module.get_forms()):
                form_name = ('{index} - {name}.xml'.format(index=form_index, name=unicode_slug(form.default_name())))
                form_path = os.path.join(module_dir, form_name)
                with open(form_path, 'w') as f:
                    f.write(form.source.encode('utf-8'))
                    print('wrote {}'.format(form_path))
