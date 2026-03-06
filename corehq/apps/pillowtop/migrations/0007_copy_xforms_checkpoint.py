from django.db import migrations
from pillowtop.utils import change_checkpoint_id


class Migration(migrations.Migration):

    dependencies = [
        ('pillowtop', '0006_add_geopoint_to_case_search_index'),
    ]

    operations = [change_checkpoint_id(
        old_id='xform-pillow-xforms_2016-07-07-report_xforms_20160824_1708-hqusers_2017-09-07',
        new_id='xform-pillow-xforms_2016-07-07-hqusers_2017-09-07',
    )]
