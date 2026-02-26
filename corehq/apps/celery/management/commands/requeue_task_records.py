import kombu.utils.json as kombu_json
from celery import current_app
from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_datetime

from corehq.apps.celery.models import TaskRecord


class Command(BaseCommand):
    """
    Requeue TaskRecord objects into the Celery broker.

    Examples::

        # Dry run (no changes made)
        $ python manage.py requeue_task_records
        $ python manage.py requeue_task_records --task-name myapp.tasks.my_task
        $ python manage.py requeue_task_records --start 2025-01-01T00:00:00

        # Actually requeue
        $ python manage.py requeue_task_records --commit
    """

    help = (
        "Requeue TaskRecord objects into the Celery broker. "
        "Runs as a dry run by default. Use --commit to requeue"
        "All records will be requeued if no options are provied. "
        "Use --task-name to filter by task, and/or "
        "--start and --end to specify a date created time window, "
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--task-name',
            help=(
                "Only requeue records matching this task name "
                "(e.g. myapp.tasks.my_task)"
            ),
        )
        parser.add_argument(
            '--start',
            help=(
                "Only requeue records created at or after this datetime "
                "(ISO 8601)"
            ),
        )
        parser.add_argument(
            '--end',
            help=(
                "Only requeue records created before or at this datetime "
                "(ISO 8601)"
            ),
        )
        parser.add_argument(
            '--commit',
            action='store_true',
            help=(
                "Actually requeue the tasks. "
                "Without this flag the command runs as a dry run."
            ),
        )

    def handle(self, task_name, start, end, commit, **options):
        start_dt = self._parse_datetime(start, '--start')
        end_dt = self._parse_datetime(end, '--end')

        records = TaskRecord.objects.all()
        if task_name:
            records = records.filter(name=task_name)
        if start_dt:
            records = records.filter(date_created__gte=start_dt)
        if end_dt:
            records = records.filter(date_created__lte=end_dt)

        records = list(records.order_by('date_created'))
        if not records:
            self.stdout.write("No matching TaskRecord objects found.")
            return

        self.stdout.write(f"Found {len(records)} TaskRecord(s) to requeue:")
        for record in records:
            self.stdout.write(f"  {record.name}")
            self.stdout.write(f"    id:      {record.task_id}")
            self.stdout.write(f"    created: {record.date_created}")

        if not commit:
            self.stdout.write(
                self.style.WARNING(
                    "\nDry run. Pass --commit to actually requeue."
                )
            )
            return

        succeeded, failed = self._requeue(records)

        self.stdout.write(f"\nDone. {succeeded} requeued, {failed} failed.")

    def _requeue(self, records):
        succeeded = 0
        failed = 0
        for record in records:
            try:
                task = current_app.tasks[record.name]
            except KeyError:
                self.stderr.write(
                    self.style.ERROR(
                        f"Task '{record.name}' is not registered. "
                        f"Skipping {record.task_id}."
                    )
                )
                failed += 1
                continue

            args = kombu_json.loads(record.args)
            kwargs = kombu_json.loads(record.kwargs)
            try:
                task.apply_async(
                    args=args, kwargs=kwargs, task_id=str(record.task_id)
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Requeued {record.task_id} ({record.name})"
                    )
                )
                succeeded += 1
            except Exception as e:
                self.stderr.write(
                    self.style.ERROR(
                        f"Failed to requeue {record.task_id} ({record.name}): "
                        f"{e}"
                    )
                )
                failed += 1

        return succeeded, failed

    def _parse_datetime(self, value, flag):
        if value is None:
            return None
        dt = parse_datetime(value)
        if dt is None:
            raise CommandError(
                f"{flag}: invalid datetime '{value}'. Use ISO 8601 format."
            )
        return dt
