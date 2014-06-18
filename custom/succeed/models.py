# Stub models file
from couchdbkit.ext.django.schema import Document
# ensure our signals get loaded at django bootstrap time
from . import signals

class _(Document): pass