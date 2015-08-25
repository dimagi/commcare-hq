import codecs
import os
import re
from django.core.management.base import LabelCommand
from django.conf import settings


class Command(LabelCommand):
    help = ("Goes through the collected LESS files after collectstatic is run "
            "and makes sure the relative paths in the imports that reference "
            "../../../../../style/static/style/less/ are changed to "
            "../../style/less/ in order to match the new directory structure of"
            " the collected static files so that less compiles properly.")
    args = ""

    def handle(self, *args, **options):
        # all the less files collected during collectstatic
        collectedless = [os.path.join(root, file)
                         for root, dir, files in os.walk(settings.STATIC_ROOT)
                         for file in files if file.endswith('.less')]
        for less_file in collectedless:
            with codecs.open(less_file, 'r', 'utf-8') as fd:
                content = fd.read()
                if content is not None:
                    B3_REGEX = r"@\{b3-import-[a-z]+-[a-z]+\}"
                    p = re.search(B3_REGEX, content)
                    if p is not None:
                        path_def = p.group(0)
                        path_file = path_def.split('-')[-2]
                        new_path = settings.LESS_B3_PATHS.get(path_file)
                        print ("[CORRECTING] %(f_name)s path in %(less_file)s: "
                               "%(new_path)s" % {
                                   'f_name': path_file,
                                   'less_file': less_file,
                                   'new_path': new_path,
                               })
                        if new_path is not None:
                            content = re.sub(B3_REGEX, new_path, content)
                        else:
                            content = None
                    else:
                        content = None
            if content is not None:
                with open(less_file, 'w') as fd:
                    fd.write(content)
