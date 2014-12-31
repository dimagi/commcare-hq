from pycco.main import template, parse, highlight, re, destination
import os
from django.core.management.base import LabelCommand
from django.conf import settings

EXAMPLES_PATH = 'corehq/apps/styleguide/examples/'
TEMPLATE_PATH = 'corehq/apps/styleguide/templates/styleguide/examples'
DOCS_TEMPLATE_PATH = 'corehq/apps/styleguide/templates/styleguide/docs'

PYTHON_TO_PYCCO = [
    'simple_crispy_form/forms.py',
    'simple_crispy_form/views.py',
    'controls_demo/forms.py',
    'controls_demo/views.py',
]
DJ_TEMPLATES_TO_PYCCO = [
    'simple_crispy_form/base.html',
    'controls_demo/base.html',
]


class Command(LabelCommand):
    help = "Prints the paths of all the static files"
    args = "save or soft"

    root_dir = settings.FILEPATH

    def handle(self, *args, **options):
        examples_dir = os.path.join(self.root_dir, EXAMPLES_PATH)
        template_dir = os.path.join(self.root_dir, TEMPLATE_PATH)
        docs_dir = os.path.join(self.root_dir, DOCS_TEMPLATE_PATH)

        with open(os.path.join(template_dir, 'doc_template.txt'), 'r') as fdoc:
            doc_template = template(fdoc.read())

        for src_file in PYTHON_TO_PYCCO:
            source = os.path.join(examples_dir, src_file)
            folder = src_file.split('/')[0]
            outdir = os.path.join(docs_dir, folder)

            with open(source, 'r') as fin:
                sections = parse(source, fin.read())
                highlight(source, sections, outdir=outdir)
                rendered = doc_template({
                    "title": src_file,
                    "sections": sections,
                    "source": source,
                })
                result = re.sub(r"__DOUBLE_OPEN_STACHE__", "{{",
                                rendered).encode("utf-8")
            print destination(source, outdir=outdir)
            with open(destination(source, outdir=outdir), "w") as fout:
                fout.write(result)

