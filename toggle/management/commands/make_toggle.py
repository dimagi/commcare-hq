from django.core.management.base import LabelCommand, CommandError
from ...models import Toggle

class Command(LabelCommand):
    help = "Makes a toggle."
    args = "<slug> *<users>"
    label = ""
     
    def handle(self, *args, **options):
        if len(args) < 1:
            raise CommandError('Have to specify a toggle slug.')
        slug = args[0]
        usernames = list(args[1:])
        toggle = Toggle(slug=slug, enabled_users=usernames)
        toggle.save()

