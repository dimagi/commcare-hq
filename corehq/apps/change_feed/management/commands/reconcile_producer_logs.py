import csv
import logging
import os
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler

from django.core.management import BaseCommand, CommandError

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
        self.sent = {}
        self.errors = {}
        self.by_type = {
            CHANGE_PRE_SEND: self.pre_send,
            CHANGE_SENT: self.sent,
            CHANGE_ERROR: self.errors
        }
        self.count_sent = 0

        self.frozen = False

    def freeze(self):
        self.frozen = True

    def add_row(self, row):
        date, trans_type, doc_type, doc_id, transaction_id = row
        if doc_type != self.doc_type:
            return

        if self.frozen:
            if trans_type == CHANGE_PRE_SEND:
                return
            if trans_type == CHANGE_SENT or (trans_type == CHANGE_ERROR and transaction_id in self.pre_send):
                self.by_type[trans_type][transaction_id] = doc_id
        else:
            self.by_type[trans_type][transaction_id] = doc_id

    def reconcile(self):
        if not self.frozen:
            self.count_sent += len(self.sent)

        for transaction_id in set(self.sent) | set(self.errors):
            try:
                del self.pre_send[transaction_id]
            except KeyError:
                pass

        errors_by_doc_id = dict(reversed(t) for t in self.errors.items())
        for doc_id in self.sent.values():
            try:
                del errors_by_doc_id[doc_id]
            except KeyError:
                pass

        self.errors = dict(reversed(t) for t in errors_by_doc_id.items())
        self.by_type[CHANGE_ERROR] = self.errors
        self.sent.clear()

    def get_results(self):
        return {
            'sent_count': self.count_sent,
            'persistent_error_count': len(self.errors),
            'unaccounted_for': len(self.pre_send),
            'unaccounted_for_ids': set(self.pre_send.values()),
        }

    def has_results(self):
        return self.errors or self.pre_send


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

    def handle(self, **options):
        date_suffix_format = None
        for handler in logger.handlers:
            if isinstance(handler, TimedRotatingFileHandler):
                date_suffix_format = handler.suffix

        if not date_suffix_format:
            raise CommandError('Could not find date format from log handler')

        num_logs_to_process = 2
        include_current_log = False

        log_files_with_dates = get_log_files_with_dates(settings.KAFKA_PRODUCER_AUDIT_FILE, date_suffix_format)
        if len(log_files_with_dates) < num_logs_to_process:
            raise CommandError(f'Not enough files to process. Only {len(log_files_with_dates)} found.')

        sorted_logs = list(sorted(log_files_with_dates, key=lambda x: x[0]))
        logs_to_process = [log[1] for log in sorted_logs[-num_logs_to_process:]]

        if include_current_log:
            logs_to_process.append(settings.KAFKA_PRODUCER_AUDIT_FILE)

        recon = Reconciliation()

        def _process_log_file(log_file):
            with open(log_file, 'r') as f:
                reader = csv.reader(f)
                for i, row in enumerate(reader):
                    recon.add_row(row)
                    if i % 10000 == 0:
                        recon.reconcile()

        # Process all but the last log file before freezing the recon
        for log in logs_to_process[:-1]:
            _process_log_file(log)

        recon.freeze()
        _process_log_file(logs_to_process[-1])
        recon.reconcile()


def get_log_files_with_dates(current_log_path, date_suffix_format):
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

    return log_files_with_dates
