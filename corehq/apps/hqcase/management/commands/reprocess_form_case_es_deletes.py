from datetime import datetime, timedelta
from django.core.management import BaseCommand

from corehq.apps.hqadmin.models import HistoricalPillowCheckpoint
from pillowtop.models import str_to_kafka_seq, KafkaCheckpoint
from pillowtop.processors.elastic import ElasticProcessor
from pillowtop.utils import get_pillow_by_name


def get_active_pillows(pillows):
    # return active pillows based on the heuristic
    #   that have their checkpoints updated in last 30 days
    active_pillows = []
    for pillow in pillows:
        pillow = get_pillow_by_name(pillow)
        last_modified = KafkaCheckpoint.objects.filter(
            checkpoint_id=pillow.checkpoint.checkpoint_id
        ).order_by('-last_modified')[0].last_modified
        if last_modified > datetime.today() - timedelta(days=30):
            active_pillows.append(pillow)
    return active_pillows


def get_form_es_pillows():
    return get_active_pillows([
        'XFormToElasticsearchPillow',
        'xform-pillow',
        'ReportXFormToElasticsearchPillow'
    ])


def get_case_es_pillows():
    return get_active_pillows([
        'CaseToElasticsearchPillow',
        'case-pillow',
        'CaseSearchToElasticsearchPillow'
    ])


class Command(BaseCommand):
    help = """
        Reprocess form or case ES deletions since a given date.
    This reprocesses the deleted form or case pillow changes based on
    HistoricalPillowCheckpoint of the given date.

        Make sure to stop pillows before running this.
    """

    def add_arguments(self, parser):
        parser.add_argument(
            'doc_type',
            help='Specify form or case'
        )
        parser.add_argument(
            'since',
            help='Date since when deletes need to be reprocessed in YYYY-MM-DD format '
        )

    def handle(self, doc_type, since, **kwargs):
        since = datetime.strptime(since, '%Y-%m-%d')
        if doc_type == 'form':
            pillows = get_form_es_pillows()
        elif doc_type == 'case':
            pillows = get_case_es_pillows()
        else:
            print("Unknown doc type {}. Specify form or case doc-type".format(doc_type))
            return

        for pillow in pillows:
            print("Processing for pillow {}".format(pillow.pillow_id))
            try:
                checkpoint = HistoricalPillowCheckpoint.objects.get(
                    date_updated=since, checkpoint_id=pillow.checkpoint.checkpoint_id)
            except HistoricalPillowCheckpoint.DoesNotExist:
                print("No HistoricalPillowCheckpoint data available for pillow {}\n".format(pillow.pillow_id))
                continue
            total_changes = 0
            deleted_changes = 0
            seq = str_to_kafka_seq(checkpoint.seq)
            es_processors = [p for p in pillow.processors if isinstance(p, ElasticProcessor)]
            for change in pillow.get_change_feed().iter_changes(since=seq, forever=False):
                total_changes += 1
                if change.deleted and change.id:
                    deleted_changes += 1
                    for processor in es_processors:
                        processor.process_change(change)
                if total_changes % 100 == 0:
                    print("Processed {} deletes out of total {} changes for pillow {}\n".format(
                        deleted_changes, total_changes, pillow.pillow_id))
        print("Finished processing all deletes sucessfully!")
