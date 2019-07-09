from __future__ import absolute_import, unicode_literals

import uuid
from datetime import datetime
from unittest import SkipTest, skipUnless

from django.conf import settings
from django.test import TestCase

from corehq.form_processor.backends.sql.dbaccessors import ShardAccessor
from corehq.form_processor.models import XFormInstanceSQL
from corehq.form_processor.tests.utils import use_sql_backend
from corehq.messaging.scheduling.scheduling_partitioned.dbaccessors import (
    save_alert_schedule_instance,
)
from corehq.messaging.scheduling.scheduling_partitioned.models import (
    AlertScheduleInstance,
)
from corehq.messaging.scheduling.scheduling_partitioned.tests.test_dbaccessors_partitioned import (
    BaseSchedulingPartitionedDBAccessorsTest,
)
from corehq.sql_db.config import partition_config
from corehq.sql_db.models import PartitionedModel
from corehq.sql_db.shard_data_management import (
    get_count_of_unmatched_models_by_shard,
)
from corehq.sql_db.tests.utils import DefaultShardingTestConfigMixIn


@use_sql_backend
@skipUnless(settings.USE_PARTITIONED_DATABASE, 'Only applicable if sharding is setup')
class ShardManagementTest(DefaultShardingTestConfigMixIn, TestCase):
    domain = 'shard-management-test'

    @classmethod
    def setUpClass(cls):
        if not settings.USE_PARTITIONED_DATABASE:
            # https://github.com/nose-devs/nose/issues/946
            raise SkipTest('Only applicable if sharding is setup')
        super(ShardManagementTest, cls).setUpClass()
        cls.p1_uuid = uuid.UUID('9d3a283a-25b6-4116-8846-d0fc8f04f50f')
        cls.p2_uuid = uuid.UUID('8440dbd6-61b1-4b2f-a310-7e1768902d04')

    def tearDown(self):
        for db in partition_config.get_form_processing_dbs():
            AlertScheduleInstance.objects.using(db).filter(domain=self.domain).delete()
            XFormInstanceSQL.objects.using(db).filter(domain=self.domain).delete()

    def test_uuids_used(self):
        self.assertEqual(ShardAccessor.get_database_for_doc(self.p1_uuid), self.db1)
        self.assertEqual(ShardAccessor.get_database_for_doc(self.p2_uuid), self.db2)

    def test_uuid_partitioning_correct(self):
        from corehq.sql_db.shard_data_management import get_count_of_models_by_shard_for_testing
        instance = BaseSchedulingPartitionedDBAccessorsTest.make_alert_schedule_instance(
            self.p1_uuid, domain=self.domain
        )
        save_alert_schedule_instance(instance)
        self.assertEqual(AlertScheduleInstance.objects.using(self.db1).count(), 1)
        matches = get_count_of_unmatched_models_by_shard(self.db1, AlertScheduleInstance)
        self.assertEqual(0, len(matches))
        all_data = get_count_of_models_by_shard_for_testing(self.db1, AlertScheduleInstance)
        self.assertEqual(1, len(all_data))
        self.assertEqual((0, 1), all_data[0])

    def test_uuid_partitioning_incorrect(self):
        instance = BaseSchedulingPartitionedDBAccessorsTest.make_alert_schedule_instance(
            self.p1_uuid, domain=self.domain
        )
        super(PartitionedModel, instance).save(using=self.db2)
        self.assertEqual(AlertScheduleInstance.objects.using(self.db2).count(), 1)
        matches = get_count_of_unmatched_models_by_shard(self.db2, AlertScheduleInstance)
        self.assertEqual(1, len(matches))
        self.assertEqual((0, 1), matches[0])

    def test_text_partitioning_correct(self):
        from corehq.sql_db.shard_data_management import get_count_of_models_by_shard_for_testing
        form = self._make_form_instance(str(self.p2_uuid))
        form.save()
        self.assertEqual(XFormInstanceSQL.objects.using(self.db2).count(), 1)
        matches = get_count_of_unmatched_models_by_shard(self.db2, XFormInstanceSQL)
        self.assertEqual(0, len(matches))
        all_data = get_count_of_models_by_shard_for_testing(self.db2, XFormInstanceSQL)
        self.assertEqual(1, len(all_data))
        self.assertEqual((2, 1), all_data[0])

    def test_text_partitioning_incorrect(self):
        form = self._make_form_instance(str(self.p2_uuid))
        super(PartitionedModel, form).save(using=self.db1)
        self.assertEqual(XFormInstanceSQL.objects.using(self.db1).count(), 1)
        matches = get_count_of_unmatched_models_by_shard(self.db1, XFormInstanceSQL)
        self.assertEqual(1, len(matches))
        self.assertEqual((2, 1), matches[0])

    @classmethod
    def _make_form_instance(cls, form_id):
        return XFormInstanceSQL(
            form_id=form_id,
            xmlns='http://openrosa.org/formdesigner/form-processor',
            received_on=datetime.utcnow(),
            user_id='a-user',
            domain=cls.domain,
            state=XFormInstanceSQL.NORMAL,

        )
