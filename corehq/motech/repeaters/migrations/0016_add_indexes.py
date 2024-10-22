from django.db import migrations, models


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("repeaters", "0015_repeater_max_workers"),
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
                        name="is_deleted_partial_idx",
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

                # Replace with a partial index on `id_` column
                migrations.RunSQL(
                    sql="""
                    CREATE INDEX CONCURRENTLY "is_deleted_partial_idx"
                        ON "repeaters_repeater" ("id_")
                        WHERE NOT "is_deleted";
                    """,
                    reverse_sql="""
                    DROP INDEX CONCURRENTLY "is_deleted_partial_idx";
                    """
                ),

                # Add partial index for RepeatRecord.state on `repeater_id`
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
