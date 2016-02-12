from django.contrib import admin
from corehq.form_processor.models import XFormInstanceSQL, CommCareCaseSQL


# note: these require ALLOW_FORM_PROCESSING_QUERIES = True in your localsettings.py to work
admin.site.register(XFormInstanceSQL)
admin.site.register(CommCareCaseSQL)
