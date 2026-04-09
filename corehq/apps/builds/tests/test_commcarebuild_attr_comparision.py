from corehq.apps.cleanup.tests.util import ModelAttrEqualityHelper
from corehq.apps.builds.models.CommCareBuild import CommCareBuild
from corehq.apps.builds.models.CommCareBuild import SQLCommCareBuild


class TestCommCareBuildModelsAttrEquality(ModelAttrEqualityHelper):

    def test_have_same_attrs(self):
        couch_attrs = self.get_cleaned_couch_attrs(CommCareBuild)
        sql_attrs = self.get_sql_attrs(SQLCommCareBuild)
        self.assertEqual(couch_attrs ^ sql_attrs, set())

    couch_only_attrs = {*[
        # removed attrs
        # renamed attrs
        # not used attrs
    ]}

    sql_only_attrs = {*[
        # new attrs
        # renamed attrs
    ]}
