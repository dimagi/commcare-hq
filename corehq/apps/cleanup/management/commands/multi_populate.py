from datetime import datetime

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand

from .populate_sql_model_from_couch_model import PopulateSQLCommand


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            'commands',
            metavar="COMMAND",
            nargs="+",
            help="""
                One or more Couch to SQL migration management commands to run.
                Intended for running multiple subclasses of PopulateSQLCommand
                in series.
            """
        )
        parser.add_argument(
            '--verify-only',
            action='store_true',
            dest='verify_only',
            default=False,
            help="""
                Don't migrate anything, instead check if couch and sql data is identical.
            """,
        )
        parser.add_argument(
            '--skip-verify',
            action='store_true',
            dest='skip_verify',
            default=False,
            help="""
                Migrate even if verifcation fails. This is intended for usage only with
                models that don't support verification.
            """,
        )
        parser.add_argument(
            '--domains',
            nargs='+',
            help="Only migrate documents in the specified domains",
        )
        parser.add_argument(
            '--log-path',
            default="-" if settings.UNIT_TESTING else None,
            help="File path to write logs to. If not provided a default will be used."
        )

    def handle(self, **options):
        if not options["log_path"]:
            date = datetime.utcnow().strftime('%Y-%m-%dT%H-%M-%S.%f')
            command_name = self.__class__.__module__.split('.')[-1]
            options["log_path"] = f"{command_name}_{date}.log"
        options["append_log"] = True
        for command in options.pop("commands"):
            print(f"\n\n{command}...")
            with PopulateSQLCommand.open_log(options["log_path"], True) as log:
                print(f"\n{command} logs:", file=log)
            call_command(command, **options)
