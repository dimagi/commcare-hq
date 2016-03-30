import os

from django.core.management.base import LabelCommand
from django.template.loader import get_template_from_string
from django.template import Context
from django.conf import settings

SQL_ACCESSOR_DIR = os.path.join(settings.FILEPATH, 'corehq', 'sql_accessors', 'sql_templates')

SQL_PROXY_ACCESSOR_DIR = os.path.join(settings.FILEPATH, 'corehq', 'sql_proxy_accessors', 'sql_templates')
TEMPLATE_NAME = '_template.sql'


class Command(LabelCommand):
    help = "Create a template sql function"
    args = "<sql_function_name.. sql_function_name>"

    def handle_label(self, sql_function_name, **options):
        sql_function_name = os.path.splitext(sql_function_name)[0]  # strip any extension

        self._create_accessor_function(sql_function_name, SQL_ACCESSOR_DIR)
        self._create_accessor_function(sql_function_name, SQL_PROXY_ACCESSOR_DIR)

    def _create_accessor_function(self, sql_function_name, accessor_dir):
        with open(os.path.join(accessor_dir, TEMPLATE_NAME)) as f:
            template_string = f.read()

        template = get_template_from_string(template_string)
        rendered_template = template.render(Context({'sql_function_name': sql_function_name}))

        with open(os.path.join(accessor_dir, '{}.sql'.format(sql_function_name)), 'w+') as f:
            f.write(rendered_template)
