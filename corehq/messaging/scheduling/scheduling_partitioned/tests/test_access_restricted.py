from corehq.messaging.scheduling.scheduling_partitioned.models import AlertScheduleInstance
from corehq.util.exceptions import AccessRestricted
from django.test import TestCase


class TestAccessRestricted(TestCase):

    def test_access_restricted(self):
        with self.assertRaises(AccessRestricted):
            [obj for obj in AlertScheduleInstance.objects.all()]

        with self.assertRaises(AccessRestricted):
            AlertScheduleInstance.objects.all()[0]

        with self.assertRaises(AccessRestricted):
            AlertScheduleInstance.objects.all()[0:10]

        with self.assertRaises(AccessRestricted):
            len(AlertScheduleInstance.objects.all())

        with self.assertRaises(AccessRestricted):
            AlertScheduleInstance.objects.count()

        with self.assertRaises(AccessRestricted):
            AlertScheduleInstance.objects.filter(schedule_instance_id=None)

        with self.assertRaises(AccessRestricted):
            AlertScheduleInstance.objects.exclude(schedule_instance_id=None)

        with self.assertRaises(AccessRestricted):
            AlertScheduleInstance.objects.get(schedule_instance_id=None)

        with self.assertRaises(AccessRestricted):
            AlertScheduleInstance.objects.create()

        with self.assertRaises(AccessRestricted):
            AlertScheduleInstance.objects.get_or_create(schedule_instance_id=None)
