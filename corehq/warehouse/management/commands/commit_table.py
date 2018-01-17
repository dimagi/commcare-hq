from __future__ import absolute_import
from datetime import datetime
from django.core.management import BaseCommand, CommandError
from corehq.warehouse.const import ALL_TABLES
from corehq.warehouse.models import get_cls_by_slug, Batch, CommitRecord


USAGE = """Usage: ./manage.py commit_table <slug> <batch_id>

Slugs:

{}

""".format('\n'.join(sorted(ALL_TABLES)))


class Command(BaseCommand):
    """
    Example: ./manage.py stage_table group_staging 222617b9-8cf0-40a2-8462-7f872e1f1344
    """
    help = USAGE

    def add_arguments(self, parser):
        parser.add_argument('slug')
        parser.add_argument('batch_id')

    def handle(self, slug, batch_id, **options):
        try:
            batch = Batch.objects.get(pk=batch_id)
        except Batch.DoesNotExist:
            raise CommandError('Invalid batch ID: {}'.format(batch_id))

        try:
            model = get_cls_by_slug(slug)
        except KeyError:
            raise CommandError('{} is not a valid slug. \n\n {}'.format(slug, USAGE))

        commit_record = CommitRecord(
            slug=slug,
            batch=batch,
            verified=False,
        )
        try:
            commit_record.verified = model.commit(batch)
        except Exception as e:
            commit_record.error = e
            commit_record.success = False
            raise
        else:
            commit_record.success = True
        finally:
            commit_record.completed_on = datetime.utcnow()
            commit_record.save()
