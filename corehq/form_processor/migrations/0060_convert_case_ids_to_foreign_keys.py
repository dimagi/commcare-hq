# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import models, migrations




class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0059_remove_ledgervalue_location_id'),
    ]

    operations = [
        # The other way to convert a field to a foreign key involves creating a new column
        # doing a data migration and then dropping the old column which seemed ridiculous to me
        migrations.RunSQL(
            'ALTER TABLE "form_processor_ledgervalue" '
            'ADD CONSTRAINT "cd40c15ceaad5d793e09d0b69eb4ed88" FOREIGN KEY ("case_id") '
            'REFERENCES "form_processor_commcarecasesql" ("case_id") DEFERRABLE INITIALLY DEFERRED',
            "ALTER TABLE form_processor_ledgervalue DROP CONSTRAINT cd40c15ceaad5d793e09d0b69eb4ed88;",
            state_operations=[
                migrations.RemoveField(
                    model_name='ledgervalue',
                    name='case_id',
                ),
                migrations.AddField(
                    model_name='ledgervalue',
                    name='case',
                    field=models.ForeignKey(to='form_processor.CommCareCaseSQL',
                                            to_field='case_id', db_index=False,
                                            on_delete=models.CASCADE),
                    preserve_default=False,
                ),
                migrations.AlterUniqueTogether(
                    name='ledgervalue',
                    unique_together=set([('case', 'section_id', 'entry_id')]),
                ),
            ]
        ),
        migrations.RunSQL(
            'ALTER TABLE "form_processor_ledgertransaction" '
            'ADD CONSTRAINT "D35e6052ba235dcd116c9c37ba096e19" FOREIGN KEY ("case_id") '
            'REFERENCES "form_processor_commcarecasesql" ("case_id") DEFERRABLE INITIALLY DEFERRED;',
            "ALTER TABLE form_processor_ledgertransaction DROP CONSTRAINT D35e6052ba235dcd116c9c37ba096e19;",
            state_operations=[
                migrations.AddField(
                    model_name='ledgertransaction',
                    name='case',
                    field=models.ForeignKey(default='__none__', to='form_processor.CommCareCaseSQL',
                                            to_field='case_id', db_index=False,
                                            on_delete=models.CASCADE),
                    preserve_default=False,
                ),
                migrations.AlterIndexTogether(
                    name='ledgertransaction',
                    index_together=set([('case', 'section_id', 'entry_id')]),
                ),
                migrations.RemoveField(
                    model_name='ledgertransaction',
                    name='case_id',
                ),
            ]
        ),
    ]
