from corehq.apps.cleanup.tests.util import ModelAttrEqualityHelper
from corehq.apps.builds.models import CommCareBuild
from corehq.apps.builds.models import CommCareMobileBuild


class TestCommCareBuildModelsAttrEquality(ModelAttrEqualityHelper):

    def test_have_same_attrs(self):
        couch_attrs = self.get_cleaned_couch_attrs(CommCareBuild)
        sql_attrs = self.get_sql_attrs(CommCareMobileBuild)
        self.assertEqual(couch_attrs ^ sql_attrs, set())

    couch_only_attrs = {*[
        # removed attrs
        'create_without_artifacts',  # can be replaced by CommCareMobileBuild.objects.create
        'major_release',  # only usage is via BuildSpec. Will consolidate after migration
        'minor_release',  # only usage is via BuildSpec. Will consolidate after migration
        'all_builds',  # can be replaced by CommCareMobileBuild.objects.all()
        # renamed attrs
        # not used attrs
        'external_blobs',
        'j2me_enabled',
    ]}

    sql_only_attrs = {*[
        # new attrs
        'couch_id',
        # renamed attrs
        # auto generated attrs
        'get_next_by_time',
        'get_previous_by_time',
    ]}
