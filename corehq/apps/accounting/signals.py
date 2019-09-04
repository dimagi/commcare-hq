from django.dispatch import Signal

subscription_upgrade_or_downgrade = Signal(providing_args=["domain"])
