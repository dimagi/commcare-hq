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
                    model_name="repeatrecord",
                    name="state",
                    field=models.PositiveSmallIntegerField(
                        choices=[
                            (1, "Pending"),
                            (2, "Failed"),
                            (4, "Succeeded"),
                            (8, "Cancelled"),
                            (16, "Empty"),
                            (32, "Invalid Payload"),
                        ],
                        db_index=True,
                        default=1,
                    ),
                ),
                migrations.AddIndex(
                    model_name="repeater",
                    index=models.Index(
                        condition=models.Q(("is_deleted", False), ("is_paused", False)),
                        fields=["next_attempt_at"],
                        name="next_attempt_at_partial_idx",
                    ),
                ),
            ],

            database_operations=[
                migrations.RunSQL(
                    sql="""
                    CREATE INDEX CONCURRENTLY "repeaters_repeatrecord_state_8055083b"
                    ON "repeaters_repeatrecord" ("state");
                    """,
                    reverse_sql="""
                    DROP INDEX CONCURRENTLY "repeaters_repeatrecord_state_8055083b";
                    """
                ),
                migrations.RunSQL(
                    sql="""
                    CREATE INDEX CONCURRENTLY "next_attempt_at_partial_idx"
                    ON "repeaters_repeater" ("next_attempt_at")
                    WHERE (NOT "is_deleted" AND NOT "is_paused");
                    """,
                    reverse_sql="""
                    DROP INDEX CONCURRENTLY "next_attempt_at_partial_idx";
                    """
                ),
            ]
        )
    ]
