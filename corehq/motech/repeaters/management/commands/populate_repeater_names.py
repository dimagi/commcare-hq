from django.core.management.base import BaseCommand
from corehq.motech.models import ConnectionSettings
from corehq.motech.repeaters.models import Repeater

CHUNKSIZE = 1000


class Command(BaseCommand):
    help = """
    Used to populate the name of repeaters where the name is None/NULL to the default value of its connection
    settings' name.
    """

    def handle(self, *args, **options):
        self.repeaters_updated_count = 0
        repeaters = self._get_repeaters_with_empty_names()
        self._total_repeaters_to_update = Repeater.objects.filter(name=None).count()
        while len(repeaters) > 0:
            self._show_progress(repeater_count=len(repeaters))
            connections = {
                cx.id: cx for cx in ConnectionSettings.objects.filter(
                    id__in=[r.connection_settings_id for r in repeaters])
            }
            for repeater in repeaters:
                repeater.name = connections[repeater.connection_settings_id].name
                repeater.save()
            repeaters = self._get_repeaters_with_empty_names()

    def _get_repeaters_with_empty_names(self):
        return Repeater.objects.filter(name=None)[:CHUNKSIZE]

    def _show_progress(self, repeater_count):
        self.repeaters_updated_count += repeater_count
        progress_percentage = 100 * (self.repeaters_updated_count / self._total_repeaters_to_update)
        self.stdout.write(f"{progress_percentage}% completed.")
