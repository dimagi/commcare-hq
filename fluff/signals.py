from django.dispatch import Signal

indicator_document_updated = Signal(providing_args=["diff"])
