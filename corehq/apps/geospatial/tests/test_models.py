from contextlib import contextmanager

from django.test import SimpleTestCase, TestCase

from shapely.geometry import Point

from ..const import GPS_POINT_CASE_PROPERTY
from ..exceptions import InvalidCoordinate, InvalidDistributionParam
from ..models import GeoConfig, GeoObject, Objective, ObjectiveAllocator
from ..utils import get_geo_case_property


class TestGeoObject(SimpleTestCase):

    def test_valid_create(self):
        geo_object = GeoObject('test', 1, 2)
        self.assertEqual(geo_object.id, 'test')
        self.assertEqual(geo_object.lon, 1)
        self.assertEqual(geo_object.lat, 2)

    def test_invalid_create(self):
        self.assertRaises(
            InvalidCoordinate,
            GeoObject,
            id='test',
            lon=182,
            lat=1
        )
        self.assertRaises(
            InvalidCoordinate,
            GeoObject,
            id='test',
            lon=1,
            lat=91
        )

    def test_get_point(self):
        geo_object = GeoObject('test', 1, 2)
        geo_point = geo_object.get_point()

        self.assertTrue(isinstance(geo_point, Point))
        self.assertEqual(geo_point.x, 1)
        self.assertEqual(geo_point.y, 2)

    def test_get_info(self):
        geo_object = GeoObject('test', 1, 2)
        geo_info = geo_object.get_info()
        self.assertEqual(geo_info, {'id': 'test', 'geometry': Point(1, 2)})


class TestObjective(SimpleTestCase):

    def test_get_info(self):
        objective = Objective('test', 1, 2)
        objective_info = objective.get_info()
        self.assertEqual(objective_info, {'id': 'test', 'geometry': Point(1, 2), 'is_assigned': False})


class TestObjectiveAllocator(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.close_user_id = 'user_1'
        cls.far_user_id = 'user_2'
        cls.close_objective_id = 'obj_a'
        cls.far_objective_id = 'obj_b'

        cls.test_users = [
            GeoObject(cls.close_user_id, 1, 1),
            GeoObject(cls.far_user_id, 3, 3)
        ]
        cls.test_objectives = [
            Objective(cls.close_objective_id, 1.01, 1.01),
            Objective(cls.far_objective_id, 10, 10)
        ]

    @contextmanager
    def _create_objective_allocator(self, max_distance, max_assignable):
        yield ObjectiveAllocator(
            self.test_users,
            self.test_objectives,
            max_distance=max_distance,
            max_assignable=max_assignable
        )

    def test_valid_create(self):
        with self._create_objective_allocator(max_distance=10, max_assignable=2) as objective_allocator:
            self.assertEqual(len(objective_allocator.users), 2)
            self.assertEqual(len(objective_allocator.objectives), 2)
            self.assertEqual(objective_allocator.max_distance, 10)
            self.assertEqual(objective_allocator.max_assignable, 2)

    def test_invalid_create(self):
        self.assertRaises(
            InvalidDistributionParam,
            ObjectiveAllocator,
            users=self.test_users,
            objectives=self.test_objectives,
            max_distance=-20,
            max_assignable=2
        )
        self.assertRaises(
            InvalidDistributionParam,
            ObjectiveAllocator,
            users=self.test_users,
            objectives=self.test_objectives,
            max_distance=5,
            max_assignable=-2
        )

    def test_allocate_objectives(self):
        with self._create_objective_allocator(max_distance=5, max_assignable=1) as objective_allocator:
            assigned = objective_allocator.allocate_objectives()

        self.assertEqual(len(assigned), 1)
        self.assertEqual(assigned, {self.close_user_id: [self.close_objective_id]})

    def test_get_unassigned_objectives(self):
        with self._create_objective_allocator(max_distance=5, max_assignable=1) as objective_allocator:
            objective_allocator.allocate_objectives()
            unassigned = objective_allocator.get_unassigned_objectives()

        self.assertEqual(len(unassigned), 1)
        self.assertEqual(unassigned[0], self.far_objective_id)


class TestGeoConfig(TestCase):

    domain = 'test-geo-config'
    geo_property = 'gps_location'

    def test_geo_config(self):
        case_property = get_geo_case_property(self.domain)
        self.assertEqual(case_property, GPS_POINT_CASE_PROPERTY)
        with self.get_geo_config():
            case_property = get_geo_case_property(self.domain)
            self.assertEqual(case_property, self.geo_property)
        case_property = get_geo_case_property(self.domain)
        self.assertEqual(case_property, GPS_POINT_CASE_PROPERTY)

    @contextmanager
    def get_geo_config(self):
        conf = GeoConfig(
            domain=self.domain,
            case_location_property_name=self.geo_property,
        )
        conf.save()
        try:
            yield conf
        finally:
            conf.delete()
