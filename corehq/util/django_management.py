from django.core.management import BaseCommand
from django.core.management.base import SystemCheckError

from corehq.util.datadog.utils import create_datadog_event


class AuditedBaseCommand(BaseCommand):
    command_name = None

    def create_parser(self, prog_name, subcommand):
        self.command_name = prog_name
        return super(AuditedBaseCommand, self).create_parser(prog_name, subcommand)

    def execute(self, *args, **options):
        self.create_datadog_event('start', args, options)
        try:
            output = super(AuditedBaseCommand, self).execute(*args, **options)
        except SystemCheckError:
            raise
        except Exception as e:
            self.create_datadog_event('stop', args, options, e)
            raise
        else:
            self.create_datadog_event('stop', args, options)
            return output

    def create_datadog_event(self, start_stop, args, options, error=None):
        text = 'args: {}\noptions: {}'.format(args, options)
        if error:
            text += '\nerror: {}'.format(error)
        event = '{}: {}'.format(self.command_name, start_stop)
        create_datadog_event(
            event, text, aggregation_key=self.command_name
        )
