from corehq.apps.commtrack.tests.util import CommTrackTest
from casexml.apps.phone.restore import generate_restore_payload
from casexml.apps.case.tests.util import check_xml_line_by_line
from casexml.apps.phone.models import SyncLog
from casexml.apps.case.xml import V2
from datetime import date, datetime
from corehq.apps.commtrack.models import Product
from lxml import etree


def long_date():
    today = date.today()
    return datetime(today.year, today.month, today.day).isoformat()


def dummy_restore_xml(sp, products):
    return """
        <ns0:balance xmlns:ns0="http://commtrack.org/stock_report" xmlns="http://openrosa.org/http/response" date="{long_date}" entity-id="{sp_id}">
            <ns0:product consumption_rate="10.0" id="{product0}" quantity="" stock_category="nodata" stockout_since=""/>
            <ns0:product consumption_rate="10.0" id="{product1}" quantity="" stock_category="nodata" stockout_since=""/>
            <ns0:product consumption_rate="10.0" id="{product2}" quantity="" stock_category="nodata" stockout_since=""/>
        </ns0:balance>
    """.format(
        sp_id=sp._id,
        long_date=long_date() + 'Z',
        product0=products[0]._id,
        product1=products[1]._id,
        product2=products[2]._id,
    )


class CommTrackXMLTest(CommTrackTest):
    def test_ota_restore(self):
        user = self.reporters['fixed']
        xml = generate_restore_payload(user.to_casexml_user(), version=V2)
        balance_block = etree.fromstring(xml).find('{http://commtrack.org/stock_report}balance')
        balance_block_string = etree.tostring(balance_block)
        [sync_log] = SyncLog.view("phone/sync_logs_by_user", include_docs=True, reduce=False).all()
        check_xml_line_by_line(
            self,
            dummy_restore_xml(
                self.sp,
                Product.by_domain(self.domain.name).all(),
            ),
            balance_block_string,
        )
