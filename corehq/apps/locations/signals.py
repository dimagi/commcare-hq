from django.dispatch import Signal
from casexml.apps.case.signals import cases_received

location_created = Signal(providing_args=['loc'])
location_edited = Signal(providing_args=['loc', 'moved'])


