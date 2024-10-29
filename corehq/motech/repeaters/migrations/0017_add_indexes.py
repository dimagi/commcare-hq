from django.db import migrations, models


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("repeaters", "0016_repeater_max_workers"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name="repeater",
                    name="is_deleted",
                    field=models.BooleanField(default=False),
                ),
                migrations.AddIndex(
                    model_name="repeater",
                    index=models.Index(
                        condition=models.Q(("is_deleted", False)),
                        fields=["id"],
                        name="deleted_partial_idx",
                    ),
                ),
                migrations.AddIndex(
                    model_name="repeater",
                    index=models.Index(
                        condition=models.Q(
                            ("is_deleted", False),
                            ("is_paused", False),
                        ),
                        fields=["id"],
                        name="active_partial_idx",
                    ),
                ),
                migrations.AddIndex(
                    model_name="repeatrecord",
                    index=models.Index(
                        condition=models.Q(("state__in", (1, 2))),
                        fields=["repeater_id"],
                        name="state_partial_idx",
                    ),
                ),
            ],

            database_operations=[
                # Drop `Repeater.id_deleted` index
                migrations.RunSQL(
                    sql="""
                    DROP INDEX CONCURRENTLY "repeaters_repeater_is_deleted_08441bf0";
                    """,
                    reverse_sql="""
                    CREATE INDEX CONCURRENTLY "repeaters_repeater_is_deleted_08441bf0"
                        ON "repeaters_repeater" ("is_deleted");
                    """
                ),

                # Replace `Repeater.id_deleted` index with a partial
                # index on `id_` column.
                # > One major reason for using a partial index is to
                # > avoid indexing common values. ... This reduces the
                # > size of the index, which will speed up those queries
                # > that do use the index.
                # > -- https://www.postgresql.org/docs/current/indexes-partial.html
                migrations.RunSQL(
                    sql="""
                    CREATE INDEX CONCURRENTLY "deleted_partial_idx"
                        ON "repeaters_repeater" ("id_")
                        WHERE NOT "is_deleted";
                    """,
                    reverse_sql="""
                    DROP INDEX CONCURRENTLY "deleted_partial_idx";
                    """
                ),

                # Add partial index for is_deleted and is_paused on `id_`
                # column.
                migrations.RunSQL(
                    sql="""
                    CREATE INDEX CONCURRENTLY "active_partial_idx"
                        ON "repeaters_repeater" ("id_")
                        WHERE (NOT "is_deleted" AND NOT "is_paused");
                    """,
                    reverse_sql="""
                    DROP INDEX CONCURRENTLY "active_partial_idx";
                    """
                ),

                # Add partial index for RepeatRecord.state on `repeater_id`
                # column. This does the heavy lifting for the queries
                # related to `RepeaterManager.all_ready()`.
                migrations.RunSQL(
                    sql="""
                    CREATE INDEX CONCURRENTLY "state_partial_idx"
                        ON "repeaters_repeatrecord" ("repeater_id_")
                        WHERE "state" IN (1, 2);
                    """,
                    reverse_sql="""
                    DROP INDEX CONCURRENTLY "state_partial_idx";
                    """
                ),
            ]
        )
    ]
