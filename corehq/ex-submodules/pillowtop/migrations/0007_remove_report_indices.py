from django.db import migrations

from corehq.util.django_migrations import skip_on_fresh_install
from corehq.elastic import get_es_new


@skip_on_fresh_install
def delete_report_indices(*args, **kwargs):
    es = get_es_new()
    for index_name in [
            'report_xforms_20160824_1708',
            'report_cases_czei39du507m9mmpqk3y01x72a3ux4p0',
    ]:
        if es.indices.exists(index_name):
            es.indices.delete(index_name)


class Migration(migrations.Migration):

    dependencies = [
        ('pillowtop', '0006_add_geopoint_to_case_search_index'),
    ]

    operations = [migrations.RunPython(
        delete_report_indices,
        reverse_code=migrations.RunPython.noop,
        elidable=True,
    )]
