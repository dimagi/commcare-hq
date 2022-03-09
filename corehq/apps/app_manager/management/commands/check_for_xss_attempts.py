import re
from datetime import datetime
from couchdbkit.exceptions import ResourceNotFound
from django.conf import settings
from django.urls import reverse
from lxml.html.clean import Cleaner

from .form_iterator import FormIteratorCommandBase, get_current_apps, get_forms
# Considering changing the naming convention since this doesn't specifically look for XSS
# It catches any sort of JS being used in the tags


class Command(FormIteratorCommandBase):

    def __init__(self):
        self.xss_attempt_found = 0
        self.total_forms = 0
        self.start_time = None
        self.iteration_key = __name__

    def process_forms(self, all, limit, reset, batchsize):
        get_apps = self.get_all_apps if all else get_current_apps

        for app in get_apps(reset, batchsize):
            for form in get_forms(app):
                xss_attempt, xss_value = form_contains_xss_attempt(form)
                if xss_attempt:
                    handle_entity_form(form, app, xss_value, self.log_file)
                    self.xss_attempt_found += 1
                self.total_forms += 1
                if limit > 0 and self.total_forms >= limit:
                    return

    def report_results(self):
        elapsed = datetime.now() - self.start_time
        self.broadcast(f'Found {self.xss_attempt_found} XSS attempts in {self.total_forms} forms')
        self.broadcast(f'Completed search in {elapsed}')


def form_contains_xss_attempt(form):
    regex = '(?<=<value>)(.*?)(?=\s*<\/value>)'
    regexoutput = '(?<=<output)(.*?)(?=\s*>)'
    cleaner = Cleaner()
    clean_html = cleaner.clean_html
    cleaner_js = Cleaner(javascript=False, safe_attrs_only=False)
    cleaner_html_js = cleaner_js.clean_html

    try:
        source = form.source
    except ResourceNotFound:
        return False

    for value in re.findall(regex, form.source):
        if '&lt;' and '&gt;' in value:
            value = value.replace("&lt;", "<").replace("&gt;", ">")
        if '<output' in value:
            for output in re.findall(regexoutput, value):
                value = value.replace(output, '')
            value = value.replace("<output>", '').replace("</output>", '')
        cleaned_js = cleaner_html_js("<div>" + value + "</div>")[5:-6]
        cleaned = clean_html("<div>" + value + "</div>")[5:-6]
        if cleaned != cleaned_js:
            return True, cleaned_js
    return False, ''


#this should be further abstracted
def handle_entity_form(form, app, value, log_file):
    print('Found XSS attempt', file=log_file)
    print(f'\tForm: {form.unique_id}, app {app._id}', file=log_file)
    print(f'\tValue: {value}', file=log_file)
    if app.copy_of:
        print(f'\tApp is a copy of {app.copy_of}. Found on version {app.version}', file=log_file)
    protocol = settings.DEFAULT_PROTOCOL
    host = settings.BASE_ADDRESS
    url = reverse('get_xform_source', args=(app.domain, app._id, form.unique_id,))
    print(f'\tview document at: {protocol}://{host}{url}', file=log_file)
