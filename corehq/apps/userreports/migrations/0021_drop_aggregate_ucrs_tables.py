from django.db import migrations


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
    ]
