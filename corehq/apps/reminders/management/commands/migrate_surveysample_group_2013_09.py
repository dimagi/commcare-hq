from django.core.management.base import LabelCommand
import sys
from corehq.apps.casegroups.models import CommCareCaseGroup


class Command(LabelCommand):
    help = "Migrate existing SurveySamples to CommCareCaseGroup documents introduced in September 2013"
    args = ""
    label = ""

    def handle(self, *labels, **options):
        existing_samples = CommCareCaseGroup.get_db().view(
            'reminders/sample_by_domain',
            startkey=[],
            endkey=[{}],
            include_docs=True
        ).all()

        print "Found %d SurveySamples to migrate..." % len(existing_samples)
        print "Migrating"

        for sample in existing_samples:
            try:
                sample_doc = sample["doc"]
                sample_doc["timezone"] = sample_doc.get("time_zone")
                del sample_doc["time_zone"]
                sample_doc["cases"] = sample_doc.get("contacts", [])
                del sample_doc["contacts"]
                sample_doc["doc_type"] = CommCareCaseGroup.__name__

                case_group = CommCareCaseGroup.wrap(sample_doc)
                case_group.save()
                sys.stdout.write('.')
            except Exception:
                sys.stdout.write('!')
            sys.stdout.flush()

        print "\nMigration complete."
