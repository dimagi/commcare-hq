from django.dispatch import Signal

location_created = Signal(providing_args=['loc'])
location_edited = Signal(providing_args=['loc', 'moved'])
