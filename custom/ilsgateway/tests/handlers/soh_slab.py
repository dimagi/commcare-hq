from corehq.apps.commtrack.models import CommtrackConfig, ConsumptionConfig
from corehq.apps.consumption.shortcuts import set_default_consumption_for_supply_point
from corehq.util.translation import localize
from custom.ilsgateway.models import SLABConfig
from custom.ilsgateway.slab.messages import REMINDER_TRANS, SOH_OVERSTOCKED
from custom.ilsgateway.tests.handlers.utils import ILSTestScript, TEST_DOMAIN
from custom.ilsgateway.slab.utils import overstocked_products


class SOHSLABTest(ILSTestScript):

    @classmethod
    def setUpClass(cls):
        super(SOHSLABTest, cls).setUpClass()
        SLABConfig.objects.create(
            is_pilot=True,
            sql_location=cls.facility.sql_location
        )
        config = CommtrackConfig.for_domain(TEST_DOMAIN)
        config.use_auto_consumption = False
        config.individual_consumption_defaults = True
        config.consumption_config = ConsumptionConfig(
            use_supply_point_type_default_consumption=True,
            exclude_invalid_periods=True
        )
        config.save()
        set_default_consumption_for_supply_point(TEST_DOMAIN, cls.id.get_id, cls.facility_sp_id, 100)
        set_default_consumption_for_supply_point(TEST_DOMAIN, cls.dp.get_id, cls.facility_sp_id, 100)
        set_default_consumption_for_supply_point(TEST_DOMAIN, cls.ip.get_id, cls.facility_sp_id, 100)

    def test_stock_on_hand_overstocked(self):
        with localize('sw'):
            reminder_trans = unicode(REMINDER_TRANS)
            soh_overstocked = unicode(SOH_OVERSTOCKED)
        script = """
            5551234 > Hmk Id 400 Dp 900 Ip 678
            5551234 < %(reminder_trans)s
        """ % {"reminder_trans": reminder_trans}
        self.run_script(script)

        stock_state = overstocked_products(self.facility.sql_location)
        self.assertListEqual([(u'dp', 900, 600), (u'ip', 678, 600)], stock_state)

        script = """
            5551234 > Hmk Id 400 Dp 900 Ip 678
            5551234 < %(reminder_trans)s
            5551234 < %(soh_overstocked)s
        """ % {"reminder_trans": reminder_trans,
               "soh_overstocked": soh_overstocked % {'overstocked_list': 'dp: 900 ip: 678',
                                                     'products_list': 'dp: 600 ip: 600'}}
        self.run_script(script)
