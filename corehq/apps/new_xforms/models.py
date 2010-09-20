from django.db import models
from couchdbkit.ext.django.schema import *

class XForm(Document):
    display_name = StringProperty()
    xmlns = StringProperty()
    submit_time = DateTimeProperty()
    domain = StringProperty()

class XFormGroup(Document):
    "Aggregate of all XForms with the same xmlns"
    display_name = StringProperty()
    xmlns = StringProperty()
