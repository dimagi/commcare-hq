from corehq.apps.app_manager.models import Application
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """
    Goes through all builds and checks whether they have forms with
    version numbers higher than the build version.

    (This has been found to cause auto-update issues)
    """

    def handle(self, *args, **options):
        builds = True
        limit = 100
        skip = 0
        while builds:
            builds = Application.view(
                'app_manager/builds_by_date',
                include_docs=True,
                reduce=False,
                limit=limit,
                skip=skip,
                reverse=True
            ).all()
            skip += limit
            for build in builds:
                if any([
                    form.version > build.version
                    for module in build.modules
                    for form in module.forms
                ]):
                    print build._id
