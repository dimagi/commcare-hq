import re
from datetime import datetime
from couchdbkit.exceptions import ResourceNotFound
from django.conf import settings
from django.urls import reverse
from lxml.html.clean import Cleaner

from ._form_iterator import FormIteratorCommandBase, get_current_apps, get_forms


class Command(FormIteratorCommandBase):

    def __init__(self):
        self.js_usage_found = 0
        self.total_forms = 0
        self.start_time = None
        self.iteration_key = __name__

    def process_forms(self, all, limit, reset, batchsize):
        get_apps = self.get_all_apps if all else get_current_apps

        for app in get_apps(reset, batchsize):
            for form in get_forms(app):
                js_usage, value = form_contains_xss_attempt(form)
                if js_usage:
                    handle_entity_form(form, app, value, self.log_file)
                    self.js_usage_found += 1
                self.total_forms += 1
                if limit > 0 and self.total_forms >= limit:
                    return

    def report_results(self):
        elapsed = datetime.now() - self.start_time
        self.broadcast(f'Found {self.js_usage_found} JS usages in {self.total_forms} forms')
        self.broadcast(f'Completed search in {elapsed}')


def form_contains_xss_attempt(form):
    match_user_input_regex = '<value>(.*?)</value>'
    try:
        source = form.source
    except ResourceNotFound:
        return False, ''

    for value in re.findall(match_user_input_regex, form.source):
        prepared_value = prepare_value(value)
        clean_html = get_cleaned_value(Cleaner(javascript=True, safe_attrs_only=True).clean_html, prepared_value)
        dirty_html = get_cleaned_value(Cleaner(javascript=False, safe_attrs_only=False).clean_html, prepared_value)
        if clean_html != dirty_html:
            return True, dirty_html
    return False, ''


def get_cleaned_value(clean_func, value):
    opening_tag = '<div>'
    closing_tag = '</div>'
    opening_tag_len = len(opening_tag)
    closing_tag_len = len(closing_tag)

    wrapped = f'{opening_tag}{value}{closing_tag}'
    return clean_func(wrapped)[opening_tag_len:-closing_tag_len]


def prepare_value(value):
    match_output_attributes_regex = '<output(.*?)>'
    if '&lt;' and '&gt;' in value:
        value = value.replace("&lt;", "<").replace("&gt;", ">")
    if '<output' in value:
        value = re.sub(match_output_attributes_regex, '', value).replace("</output>", '')
    return value


def handle_entity_form(form, app, value, log_file):
    print('Found JS usage', file=log_file)
    print(f'\tForm: {form.unique_id}, app {app._id}', file=log_file)
    print(f'\tValue: {value}', file=log_file)
    if app.copy_of:
        print(f'\tApp is a copy of {app.copy_of}. Found on version {app.version}', file=log_file)
    protocol = settings.DEFAULT_PROTOCOL
    host = settings.BASE_ADDRESS
    url = reverse('get_xform_source', args=(app.domain, app._id, form.unique_id,))
    print(f'\tview document at: {protocol}://{host}{url}', file=log_file)
