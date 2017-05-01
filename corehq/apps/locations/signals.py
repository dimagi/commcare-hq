from django.dispatch import Signal

# Called after location validation, before save.
# Used for additional validation or modification.
clean_location = Signal(providing_args=["domain", "request_user", "location", "forms"])
location_edited = Signal(providing_args=['loc', 'moved'])
