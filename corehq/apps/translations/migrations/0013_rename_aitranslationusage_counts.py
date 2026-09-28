from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('translations', '0012_aitranslation_aitranslationconfig_aitranslationusage'),
    ]

    operations = [
        migrations.RenameField(
            model_name='aitranslationusage',
            old_name='word_count',
            new_name='words_translated',
        ),
        migrations.RenameField(
            model_name='aitranslationusage',
            old_name='string_count',
            new_name='strings_translated',
        ),
    ]
