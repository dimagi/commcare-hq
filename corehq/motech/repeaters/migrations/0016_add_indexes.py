"""
Adds an index for RepeatRecord.state and a partial index for
next_attempt_at + not_paused. The indexes are used by
RepeaterManager.all_ready() to select all Repeaters that have
RepeatRecords that are ready to be sent.
"""
from django.db import migrations


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("repeaters", "0015_repeater_max_workers"),
    ]

    operations = [
        # Adds an index for RepeatRecord.state. Builds it concurrently.
        # The SQL and the index name were determined from the generated
        # Django migration. The migration was made concurrent by setting
        # `atomic = False` and adding "CONCURRENTLY" to the SQL.
        migrations.RunSQL(
            sql="""
            CREATE INDEX CONCURRENTLY "repeaters_repeatrecord_state_8055083b"
            ON "repeaters_repeatrecord" ("state");
            """,
            reverse_sql="""
            DROP INDEX CONCURRENTLY "repeaters_repeatrecord_state_8055083b";
            """
        ),

        # Adds an index for Repeater.next_attempt_at when
        # Repeater.is_paused is False. Builds it concurrently.
        migrations.RunSQL(
            sql="""
            CREATE INDEX CONCURRENTLY "next_attempt_at_not_paused_idx"
            ON "repeaters_repeater" ("next_attempt_at")
            WHERE NOT "is_paused";
            """,
            reverse_sql="""
            DROP INDEX CONCURRENTLY "next_attempt_at_not_paused_idx";
            """
        )
    ]
