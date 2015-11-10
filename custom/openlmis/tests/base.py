from corehq.apps.commtrack.models import OpenLMISConfig, CommtrackConfig
from corehq.apps.commtrack.tests.util import CommTrackTest
from custom.openlmis.tests.mock_api import MockOpenLMISEndpoint


class OpenLMISTestBase(CommTrackTest):
    requisitions_enabled = True

    def setUp(self):
        super(OpenLMISTestBase, self).setUp()
        self.api = MockOpenLMISEndpoint("uri://mock/lmis/endpoint", username='ned', password='honor')

        openlmis_config = OpenLMISConfig()
        openlmis_config.enabled = True

        commtrack_config = CommtrackConfig.for_domain(self.domain.name)
        commtrack_config.openlmis_config = openlmis_config
        commtrack_config.save()

