from django.contrib.staticfiles.management.commands.collectstatic import Command as CollectStaticCommand

# TODO Use a different destnation for it

class Command(CollectStaticCommand):
    def get_targets(self):
        apps = [
            "hqwebapp",
            "styleguide",
        ]
        return [app for app in super().get_targets() if app in apps]
