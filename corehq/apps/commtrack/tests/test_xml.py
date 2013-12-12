from corehq.apps.commtrack.tests.util import CommTrackTest
from casexml.apps.phone.restore import generate_restore_payload
from casexml.apps.case.tests.util import check_xml_line_by_line
from casexml.apps.phone.models import SyncLog
from casexml.apps.case.xml import V2
from datetime import date, datetime
from corehq.apps.commtrack.models import Product


def long_date():
    today = date.today()
    return datetime(today.year, today.month, today.day).isoformat()


def dummy_restore_xml(restore_id, user, sp, products):
    return """
        <OpenRosaResponse xmlns="http://openrosa.org/http/response">
            <message nature="ota_restore_success">Successfully restored account commtrack-user-fixed!</message>
            <Sync xmlns="http://commcarehq.org/sync">
                <restore_id>{restore_id}</restore_id>
            </Sync>
            <Registration xmlns="http://openrosa.org/user/registration">
                <username>commtrack-user-fixed</username>
                <password>{password}</password>
                <uuid>{uuid}</uuid>
                <date>{date}</date>
                <user_data>
                    <data key="commtrack_requester">True</data>
                    <data key="commtrack_receiver">True</data>
                </user_data>
            </Registration>
            <fixture id="user-groups" user_id="{uuid}">
                <groups>
                    <group id="{group_id}">
                        <name>commtrack-folks</name>
                    </group>
                </groups>
            </fixture>
            <case xmlns="http://commcarehq.org/case/transaction/v2" case_id="{sp_id}" date_modified="{long_date}" user_id="commtrack-system">
                <create>
                    <case_type>supply-point</case_type>
                    <case_name>loc1</case_name>
                    <owner_id>{group_id}</owner_id>
                </create>
                <update>
                    <location_id>{location_id}</location_id>
                </update>
            </case>
            <balance entity-id="{sp_id}" date="{long_date}">
                <product index="0" id="{product0}" quantity="0"/>
                <product index="1" id="{product1}" quantity="0"/>
                <product index="2" id="{product2}" quantity="0"/>
            </balance>
        </OpenRosaResponse>
    """.format(
        restore_id=restore_id,
        password=user.password,
        uuid=user._id,
        group_id=user.get_group_ids()[0],
        sp_id=sp._id,
        date=date.today().isoformat(),
        long_date=long_date(),
        location_id=user.location,
        product0=products[0]._id,
        product1=products[1]._id,
        product2=products[2]._id,
    )


class CommTrackXMLTest(CommTrackTest):
    def test_ota_restore(self):
        user = self.reporters['fixed']
        xml = generate_restore_payload(user.to_casexml_user(), version=V2)
        [sync_log] = SyncLog.view("phone/sync_logs_by_user", include_docs=True, reduce=False).all()
        check_xml_line_by_line(
            self,
            dummy_restore_xml(
                sync_log.get_id,
                user,
                self.sp,
                Product.by_domain(self.domain.name).all(),
            ),
            xml,
        )
