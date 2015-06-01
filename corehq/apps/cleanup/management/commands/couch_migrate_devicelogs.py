from corehq.apps.cleanup.management.commands.couch_migrate import Command as MigrateCommand
from corehq.pillows.migration import DeviceLogMigrationPillow


class Command(MigrateCommand):
    pillow_class = DeviceLogMigrationPillow
