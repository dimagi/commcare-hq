import codecs
import os
from django.core.management.base import LabelCommand
from django.conf import settings

NON_COLLECTED_PATH = '../../../../../style/static/style/less/'
COLLECTED_PATH = '../../style/less/'


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
                if NON_COLLECTED_PATH in content:
                    print "[FIXING] bad less import in %s" % less_file
                    content = content.replace(NON_COLLECTED_PATH, COLLECTED_PATH)
                else:
                    content = None
            if content is not None:
                with open(less_file, 'w') as fd:
                    fd.write(content)
