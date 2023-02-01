import re

from django.test import SimpleTestCase

from corehq.apps.app_manager.models import (
    Application,
)
from corehq.apps.app_manager.tests.util import (
    SuiteMixin,
    TestXmlMixin,
    commtrack_enabled,
    patch_get_xform_resource_overrides,
)
from corehq.apps.app_manager.xpath import session_var


@patch_get_xform_resource_overrides()
class SuiteCommtrackTest(SimpleTestCase, SuiteMixin):
    file_path = ('data', 'suite')

    @commtrack_enabled(True)
    def test_product_list_custom_data(self, *args):
        # product data shouldn't be interpreted as a case index relationship
        app = Application.wrap(self.get_json('suite-advanced'))
        custom_path = 'product_data/is_bedazzled'
        app.modules[1].product_details.short.columns[0].field = custom_path
        suite_xml = app.create_suite()
        for xpath in ['/template/text/xpath', '/sort/text/xpath']:
            self.assertXmlPartialEqual(
                '<partial><xpath function="{}"/></partial>'.format(custom_path),
                suite_xml,
                './detail[@id="m1_product_short"]/field[1]' + xpath,
            )

    @commtrack_enabled(True)
    def test_autoload_supplypoint(self, *args):
        app = Application.wrap(self.get_json('app'))
        app.modules[0].forms[0].source = re.sub('/data/plain',
                                                session_var('supply_point_id'),
                                                app.modules[0].forms[0].source)
        app_xml = app.create_suite()
        self.assertXmlPartialEqual(
            self.get_xml('autoload_supplypoint'),
            app_xml,
            './entry[1]'
        )
