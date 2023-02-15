import os.path

from django.conf import settings
from django.core.management import call_command, CommandError
from django.core.management.base import BaseCommand


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
            '--chunk-size',
            type=int,
            default=1000,
            help="Number of docs to fetch at once (default: 100).",
        )
        parser.add_argument(
            '--log-dir',
            default="-" if settings.UNIT_TESTING else None,
            help="Directory to write logs to. Defaults to the current directory."
        )

    def handle(self, commands, log_dir=None, **options):
        if log_dir:
            if not os.path.isdir(log_dir):
                raise CommandError("--log-dir must specify a directory.")
            options["log_path"] = log_dir
        for command in commands:
            print(f"\n\n{command}...")
            call_command(command, **options)
