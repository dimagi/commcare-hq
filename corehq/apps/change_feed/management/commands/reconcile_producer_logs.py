import csv
import inspect
import logging
import os
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler

from django.core.mail import mail_admins
from django.core.management import BaseCommand, CommandError
from django.template import engines

import settings
from corehq.apps.change_feed.producer import (
    CHANGE_ERROR,
    CHANGE_PRE_SEND,
    CHANGE_SENT,
    KAFKA_AUDIT_LOGGER,
)

logger = logging.getLogger(KAFKA_AUDIT_LOGGER)


class DocTypeReconciliation(object):
    """Reconcile Kafka producer transactions. Each attempt to send has a unique
    transaction ID which is used by the reconciliation.

    Transactions are processed until point A at which stage the reconcilliation is 'frozen'.
    Transactions seen after the 'freeze' will only be used to reconcile transactions seen before the freeze
    and will not be added to the list of transactions to reconcile.
    """
    def __init__(self, doc_type):
        self.doc_type = doc_type
        self.pre_send = {}
        self.error_doc_ids = set()
        self.count = 0

        self.frozen = False

    def freeze(self):
        self.frozen = True

    def add_row(self, row):
        date, trans_type, doc_type, doc_id, transaction_id = row
        if doc_type != self.doc_type:
            return

        if trans_type == CHANGE_PRE_SEND and not self.frozen:
            self.count += 1
            self.pre_send[transaction_id] = doc_id
        elif trans_type == CHANGE_SENT:
            try:
                del self.pre_send[transaction_id]
            except KeyError:
                pass
            try:
                self.error_doc_ids.remove(doc_id)
            except KeyError:
                pass
        if trans_type == CHANGE_ERROR and (not self.frozen or transaction_id in self.pre_send):
            try:
                del self.pre_send[transaction_id]
            except KeyError:
                pass
            self.error_doc_ids.add(doc_id)

    def get_results(self):
        return {
            'transaction_count': self.count,
            'persistent_error_count': len(self.error_doc_ids),
            'unaccounted_for': len(self.pre_send),
            'unaccounted_for_ids': set(self.pre_send.values()),
        }

    def has_results(self):
        return self.error_doc_ids or self.pre_send


class Reconciliation(object):
    def __init__(self):
        self.by_doc_type = {}

    def freeze(self):
        for doc_type_recon in self.by_doc_type.values():
            doc_type_recon.freeze()

    def add_row(self, row):
        doc_type = row[2]
        if doc_type not in self.by_doc_type:
            self.by_doc_type[doc_type] = DocTypeReconciliation(doc_type)
        self.by_doc_type[doc_type].add_row(row)

    def reconcile(self):
        for doc_type_recon in self.by_doc_type.values():
            doc_type_recon.reconcile()

    def get_results(self):
        return {
            doc_type: recon.get_results()
            for doc_type, recon in self.by_doc_type.items()
            if recon.has_results()
        }


class Command(BaseCommand):
    help = """"Kafka Producer log file reconciliation command.

    This command will process kafka producer audit logs to look for transactions that were initiated
    but not completed.

    The recon process will read new transactions from '-n' log files. After that it will continue to look
    for completion logs in '-f' log files.

    e.g. -n 2 -f 1
        logA: process all logs
        logB: process all logs
        logC: only process completion logs (don't add new transactions to the recon)

    Any transactions that have not been completed by the end of the processing
    will be considered unaccounted for.
    """

    def add_arguments(self, parser):
        parser.add_argument(
            '-n', dest='pre_logs', type=int, default=1,
            help='Number of historical log files to process for new transactions')
        parser.add_argument(
            '-f', dest='post_logs', type=int, default=1,
            help='Number of additional log files to process for completion logs')
        parser.add_argument(
            '--include-current', action='store_true',
            help='Include the current log file in the list of files to check for completion logs')
        parser.add_argument(
            '--notify', action='store_true', help='Send notification with recon summary')

    def handle(self, pre_logs, post_logs, include_current, notify, **options):
        date_suffix_format = None
        for handler in logger.handlers:
            if isinstance(handler, TimedRotatingFileHandler):
                date_suffix_format = handler.suffix

        if not date_suffix_format:
            raise CommandError('Could not find date format from log handler')

        num_logs_to_process = pre_logs + post_logs
        if include_current:
            num_logs_to_process -= 1

        log_files = get_log_files(settings.KAFKA_PRODUCER_AUDIT_FILE, date_suffix_format)
        if len(log_files) < num_logs_to_process:
            raise CommandError(f'Not enough files to process. Only {len(log_files)} found.')

        logs_to_process = log_files[-num_logs_to_process:]

        if include_current:
            logs_to_process.append(settings.KAFKA_PRODUCER_AUDIT_FILE)

        recon = Reconciliation()

        def _process_log_file(log_file):
            with open(log_file, 'r') as f:
                reader = csv.reader(f)
                for i, row in enumerate(reader):
                    recon.add_row((row))

        # Process all but the last log file before freezing the recon
        for log in logs_to_process[:pre_logs]:
            _process_log_file(log)

        recon.freeze()

        for log in logs_to_process[pre_logs:pre_logs + post_logs]:
            _process_log_file(log)

        django_engine = engines['django']
        template = django_engine.from_string(inspect.cleandoc("""
            Files processed:
            {% for log in logs_to_process %}
              - {{ log }}
            {% endfor %}

            {% for res in doc_type_results %}
            {{ res }}
            {% endfor %}
        """))
        sub_template = django_engine.from_string(inspect.cleandoc("""
            Results for {{ doc_type }}:
                Transactions processed: {{ transaction_count }}
                Persistent errors: {{ persistent_error_count }}
                Unaccounted for transaction count: {{ unaccounted_for }}
                {% if unaccounted_for_ids %}
                Doc IDs unaccounted for:
                {% for doc_id in unaccounted_for_ids %}
                  - {{ doc_id }}
                {% endfor %}
                {% endif %}
        """))
        doc_type_results = []
        for doc_type, results in recon.get_results().items():
            results['doc_type'] = doc_type
            doc_type_results.append(sub_template.render(results))

        context = {
            'logs_to_process': logs_to_process,
            'doc_type_results': doc_type_results
        }
        message = template.render(context)

        if notify:
            mail_admins(
                "Kakfa producer reconciliation results",
                message
            )
        else:
            print(message)


def get_log_files(current_log_path, date_suffix_format):
    log_files = []
    current_log_file = os.path.basename(current_log_path)
    log_root, log_filename = os.path.split(current_log_path)
    for path in os.listdir(log_root):
        if os.path.isfile(path) and path.startswith(log_filename) and path != current_log_file:
            log_files.append(os.path.join(log_root, path))

    log_files_with_dates = []
    for path in log_files:
        date_part = path.split('.')[-1]
        try:
            date = datetime.strptime(date_part, date_suffix_format)
        except ValueError:
            pass  # log file format changed
        else:
            log_files_with_dates.append((date, path))

    return [log[1] for log in sorted(log_files_with_dates, key=lambda x: x[0])]
