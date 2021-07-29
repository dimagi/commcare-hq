from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('repeaters', '0004_attempt_strings'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='RepeaterStub',
            new_name='SQLRepeater',
        ),
        migrations.RemoveIndex(
            model_name='sqlrepeater',
            name='repeaters_r_domain_23d304_idx',
        ),
        migrations.RemoveIndex(
            model_name='sqlrepeater',
            name='repeaters_r_repeate_4c833b_idx',
        ),
        migrations.AddIndex(
            model_name='sqlrepeater',
            index=models.Index(
                fields=['domain'],
                name='repeaters_s_domain_bc4f14_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='sqlrepeater',
            index=models.Index(
                fields=['repeater_id'],
                name='repeaters_s_repeate_1c1c97_idx',
            ),
        ),
        migrations.RenameField(
            model_name='sqlrepeatrecord',
            old_name='repeater_stub',
            new_name='repeater',
        ),
    ]
