from django.db import migrations
from corehq.util.django_migrations import skip_on_fresh_install
from pillowtop.models import KafkaCheckpoint


@skip_on_fresh_install
def copy_xforms_checkpoint(*args, **kwargs):
    old_checkpoint_id = 'xform-pillow-xforms_2016-07-07-report_xforms_20160824_1708-hqusers_2017-09-07'
    new_checkpoint_id = 'xform-pillow-xforms_2016-07-07-hqusers_2017-09-07'

    for old in KafkaCheckpoint.objects.filter(checkpoint_id=old_checkpoint_id):
        KafkaCheckpoint.objects.create(
            checkpoint_id=new_checkpoint_id,
            topic=old.topic,
            partition=old.partition,
            offset=old.offset,
            doc_modification_time=old.doc_modification_time,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('pillowtop', '0006_add_geopoint_to_case_search_index'),
    ]

    operations = [migrations.RunPython(
        copy_xforms_checkpoint,
        reverse_code=migrations.RunPython.noop,
        elidable=True,
    )]
