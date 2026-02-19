from django.db import migrations

from corehq.util.couch_helpers import paginate_view
from corehq.util.django_migrations import skip_on_fresh_install
from corehq.util.log import with_progress_bar


@skip_on_fresh_install
def _delete_aggregate_report_configs(apps, schema_editor):
    from corehq.apps.userreports.models import ReportConfiguration
    db = ReportConfiguration.get_db()
    count = db.view(
        'all_docs/by_doc_type',
        startkey=['ReportConfiguration'],
        endkey=['ReportConfiguration', {}],
        reduce=True,
    ).one()['value']
    rows = paginate_view(
        db,
        'all_docs/by_doc_type',
        chunk_size=100,
        startkey=['ReportConfiguration'],
        endkey=['ReportConfiguration', {}],
        reduce=False,
        include_docs=True,
    )
    for row in with_progress_bar(rows, length=count, prefix='Scanning ReportConfigurations'):
        doc = row['doc']
        if doc.get('data_source_type') == 'aggregate':
            print(f"Deleting aggregate ReportConfiguration {doc['_id']} "
                  f"(domain={doc.get('domain')}, title={doc.get('title')})")
            db.delete_doc(doc)


class Migration(migrations.Migration):

    dependencies = [
        ("userreports", "0020_delete_ucr_comparison_models"),
    ]

    operations = [
        migrations.RunSQL(
            "DROP TABLE IF EXISTS aggregate_ucrs_secondarycolumn",
            migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            "DROP TABLE IF EXISTS aggregate_ucrs_primarycolumn",
            migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            "DROP TABLE IF EXISTS aggregate_ucrs_secondarytabledefinition",
            migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            "DROP TABLE IF EXISTS aggregate_ucrs_aggregatetabledefinition",
            migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            "DROP TABLE IF EXISTS aggregate_ucrs_timeaggregationdefinition",
            migrations.RunSQL.noop,
        ),
        migrations.RunPython(
            _delete_aggregate_report_configs,
            reverse_code=migrations.RunPython.noop,
            elidable=True,
        ),
    ]
