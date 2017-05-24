from django.dispatch import Signal

location_edited = Signal(providing_args=['loc', 'moved'])
