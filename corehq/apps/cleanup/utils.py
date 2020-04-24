import sys

from django.conf import settings
from django.core.management import color_style


def abort():
    print("Aborting")
    sys.exit(1)


def confirm_destructive_operation():
    style = color_style()
    print(style.ERROR("\nHEY! This is wicked dangerous, pay attention."))
    print(style.WARNING("\nThis operation irreversibly deletes a lot of stuff."))
    print(f"\nSERVER_ENVIRONMENT = {settings.SERVER_ENVIRONMENT}")

    if settings.IS_SAAS_ENVIRONMENT:
        print("This command isn't meant to be run on a SAAS environment")
        abort()

    confirm("Are you SURE you want to proceed?")


def confirm(msg):
    print(msg)
    if input("(y/N)") != 'y':
        abort()
