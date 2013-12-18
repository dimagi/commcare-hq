from corehq.apps.commtrack.tests.util import CommTrackTest, get_ota_balance_xml
from casexml.apps.case.tests.util import check_xml_line_by_line
from corehq.apps.commtrack.models import Product
from corehq.apps.commtrack.tests.data.balances import blank_balances


class CommTrackXMLTest(CommTrackTest):
    def test_ota_blank_balances(self):
        user = self.reporters['fixed']

        check_xml_line_by_line(
            self,
            blank_balances(
                self.sp,
                Product.by_domain(self.domain.name).all(),
            ),
            get_ota_balance_xml(user),
        )
