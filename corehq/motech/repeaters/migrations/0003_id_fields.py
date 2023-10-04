# Generated by Django 3.2.20 on 2023-08-21 19:39

from django.db import migrations, models
from django.db.models.deletion import DO_NOTHING

import corehq.sql_db.fields


class Migration(migrations.Migration):

    dependencies = [
        ('repeaters', '0002_repeaters_db'),
    ]

    operations = [
        migrations.RunSQL(
            sql="DROP INDEX IF EXISTS repeaters_repeater_domain_b537389f_like",
            reverse_sql="""
            CREATE INDEX IF NOT EXISTS repeaters_repeater_domain_b537389f_like
                ON repeaters_repeater (domain varchar_pattern_ops)
            """,
            state_operations=[migrations.AlterField(
                model_name='repeater',
                name='domain',
                field=corehq.sql_db.fields.CharIdField(db_index=True, max_length=126),
            )],
        ),
        migrations.AlterField(
            model_name='sqlrepeatrecord',
            name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
        migrations.AlterField(
            model_name='sqlrepeatrecordattempt',
            name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
        migrations.RunSQL(
            # Requires "repeaters_repeatrecord" to be empty
            sql="""
            CREATE FUNCTION set_default_repeaters_repeater_id()
                RETURNS trigger LANGUAGE plpgsql AS $BODY$
                BEGIN
                    IF NEW.id_ IS NULL THEN
                        NEW.id_ = NEW.repeater_id::uuid;
                    ELSIF NEW.repeater_id IS NULL THEN
                        NEW.repeater_id = REPLACE(NEW.id_::varchar, '-', '');
                    END IF;
                    RETURN NEW;
                END
                $BODY$;
            SET CONSTRAINTS "repeaters_repeatreco_repeater_id_01b51f9d_fk_repeaters" IMMEDIATE;
            ALTER TABLE "repeaters_repeatrecord"
                DROP CONSTRAINT "repeaters_repeatreco_repeater_id_01b51f9d_fk_repeaters",
                ADD COLUMN "repeater_id_" uuid NOT NULL,
                ALTER COLUMN repeater_id DROP NOT NULL;
            ALTER TABLE "repeaters_repeater" ADD COLUMN "id_" uuid;
            ALTER TABLE "repeaters_repeater"
                ADD CONSTRAINT "repeaters_repeater_id_key" UNIQUE ("id"),
                DROP CONSTRAINT "repeaters_repeater_pkey",
                ALTER COLUMN "id_" TYPE uuid USING "repeater_id"::uuid,
                ADD CONSTRAINT "repeaters_repeater_pkey" PRIMARY KEY ("id_"),
                ADD CONSTRAINT id_eq CHECK ("id_" = "repeater_id"::uuid);
            CREATE TRIGGER repeaters_repeater_default_id BEFORE INSERT ON repeaters_repeater
                FOR EACH ROW EXECUTE FUNCTION set_default_repeaters_repeater_id();
            ALTER TABLE repeaters_repeatrecord
                ADD CONSTRAINT repeaters_repeatreco_repeater_id_01b51f9d_fk_repeaters
                    FOREIGN KEY (repeater_id_) REFERENCES repeaters_repeater(id_)
                    ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED;
            ALTER TABLE repeaters_repeatrecordattempt
                DROP CONSTRAINT repeaters_repeatrecordattempt_repeat_record_id_cc88c323_fk,
                ADD CONSTRAINT repeaters_repeatrecordattempt_repeat_record_id_cc88c323_fk
                    FOREIGN KEY (repeat_record_id) REFERENCES repeaters_repeatrecord(id)
                    ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED;
            """,
            reverse_sql="""
            SET CONSTRAINTS "repeaters_repeatreco_repeater_id_01b51f9d_fk_repeaters" IMMEDIATE;
            ALTER TABLE "repeaters_repeatrecord"
                DROP CONSTRAINT repeaters_repeatreco_repeater_id_01b51f9d_fk_repeaters,
                DROP COLUMN "repeater_id_",
                ALTER COLUMN repeater_id SET NOT NULL;
            DROP TRIGGER repeaters_repeater_default_id ON repeaters_repeater;
            DROP FUNCTION set_default_repeaters_repeater_id();
            ALTER TABLE "repeaters_repeater"
                DROP CONSTRAINT "repeaters_repeater_pkey",
                DROP CONSTRAINT id_eq,
                DROP COLUMN "id_",
                ADD CONSTRAINT "repeaters_repeater_pkey" PRIMARY KEY ("id"),
                DROP CONSTRAINT "repeaters_repeater_id_key";
            ALTER TABLE repeaters_repeatrecord
                ADD CONSTRAINT repeaters_repeatreco_repeater_id_01b51f9d_fk_repeaters
                    FOREIGN KEY (repeater_id) REFERENCES repeaters_repeater(id)
                    DEFERRABLE INITIALLY DEFERRED;
            ALTER TABLE repeaters_repeatrecordattempt
                DROP CONSTRAINT repeaters_repeatrecordattempt_repeat_record_id_cc88c323_fk,
                ADD CONSTRAINT repeaters_repeatrecordattempt_repeat_record_id_cc88c323_fk
                    FOREIGN KEY (repeat_record_id) REFERENCES repeaters_repeatrecord(id)
                    DEFERRABLE INITIALLY DEFERRED;
            """,
            state_operations=[
                migrations.AlterField(
                    model_name='repeater',
                    name='id',
                    field=models.UUIDField(db_column="id_", primary_key=True, serialize=False),
                ),
                migrations.AlterField(
                    model_name='sqlrepeatrecord',
                    name='repeater',
                    field=models.ForeignKey(
                        db_column='repeater_id_',
                        on_delete=DO_NOTHING,
                        related_name='repeat_records',
                        to='repeaters.repeater',
                    ),
                ),
                migrations.AlterField(
                    model_name='sqlrepeatrecordattempt',
                    name='repeat_record',
                    field=models.ForeignKey(on_delete=DO_NOTHING, to='repeaters.sqlrepeatrecord'),
                ),
            ],
        ),
    ]
