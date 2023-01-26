from django.core.management.base import BaseCommand
from corehq.motech.repeaters.models import SQLRepeater

CHUNKSIZE = 1000


class Command(BaseCommand):
    help = """
    Used to populate the name of repeaters where the name is None/NULL to the default value of its connection
    settings' name.
    """

    def handle(self, *args, **options):
        self.repeaters_updated_count = 0
        repeaters = self._get_repeaters_with_empty_names()
        self._total_repeaters_to_update = SQLRepeater.objects.filter(name=None).count()
        while len(repeaters) > 0:
            self._show_progress(repeater_count=len(repeaters))
            for repeater in repeaters:
                repeater.name = repeater.connection_settings.name
                repeater.save()
            repeaters = self._get_repeaters_with_empty_names()

    def _get_repeaters_with_empty_names(self):
        return SQLRepeater.objects.filter(name=None).select_related('connection_settings')[:CHUNKSIZE]

    def _show_progress(self, repeater_count):
        self.repeaters_updated_count += repeater_count
        progress_percentage = 100 * (self.repeaters_updated_count / self._total_repeaters_to_update)
        self.stdout.write(f"{progress_percentage}% completed.")
