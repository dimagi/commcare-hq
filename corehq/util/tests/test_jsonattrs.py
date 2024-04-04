import json
from datetime import date

from attrs import asdict, define, field
from attrs.exceptions import NotAnAttrsClassError
from django.core.exceptions import ValidationError
from django.db import models
from testil import assert_raises, eq

from ..jsonattrs import AttrsDict, AttrsList, dict_of, list_of
from ..test_utils import unregistered_django_model


def test_attrsdict():
    @unregistered_django_model
    class Check(models.Model):
        points = AttrsDict(Point)

    points = {}
    check = Check(points=points)
    assert check.points is points, (check.points, points)

    check.points = xydict = {"north": Point(0, 1)}
    eq(get_json_value(check, "points"), {"north": {"x": 0, "y": 1}})

    set_json_value(check, "points", {"north": {"x": 0, "y": 1}})
    assert check.points is not xydict, xydict
    eq(check.points, {"north": Point(0, 1)})

    with assert_raises(ValidationError, msg=(
        '["'
        "'points' field value has an invalid format: "
        "Cannot construct Point with {} -> "
        "TypeError: __init__() missing 2 required positional arguments: 'x' and 'y'"
        '"]'
    )):
        set_json_value(check, "points", {"north": {}})


def test_attrsdict_list_of():
    @unregistered_django_model
    class Check(models.Model):
        point_lists = AttrsDict(list_of(Point))

    points = {}
    check = Check(point_lists=points)
    assert check.point_lists is points, (check.point_lists, points)

    check.point_lists = north_points = {"north": [Point(0, 1)]}
    eq(get_json_value(check, "point_lists"), {"north": [{"x": 0, "y": 1}]})

    set_json_value(check, "point_lists", {"north": [{"x": 0, "y": 1}]})
    assert check.point_lists is not north_points, north_points
    eq(check.point_lists, {"north": [Point(0, 1)]})

    check.point_lists = {"null": None}
    with assert_raises(ValueError, msg="expected list of Point, got None"):
        get_json_value(check, "point_lists")

    with assert_raises(ValidationError, msg=(
        '["'
        "'point_lists' field value has an invalid format: "
        "Cannot construct list_of(Point) with 500 -> "
        "TypeError: 'int' object is not iterable"
        '"]'
    )):
        set_json_value(check, "point_lists", {"north": 500})


def test_attrslist():
    @unregistered_django_model
    class Check(models.Model):
        values = AttrsList(Value)

    values = []
    check = Check(values=values)
    assert check.values is values, (check.values, values)

    check.values = abbylist = [Value("abby")]
    eq(get_json_value(check, "values"), [{"name": "abby"}])

    set_json_value(check, "values", [{"name": "abby"}])
    assert check.values is not abbylist, abbylist
    eq(check.values, [Value("abby")])

    with assert_raises(ValidationError, msg=(
        '["'
        "'values' field value has an invalid format: "
        "Cannot construct Value with 'bad value' -> "
        "TypeError: corehq.util.tests.test_jsonattrs.Value() "
        "argument after ** must be a mapping, not str"
        '"]'
    )):
        set_json_value(check, "values", ["bad value"])


def test_attrslist_dict_of():
    @unregistered_django_model
    class Check(models.Model):
        value_items = AttrsList(dict_of(Value))

    values = []
    check = Check(value_items=values)
    assert check.value_items is values, (check.value_items, values)

    check.value_items = nomnom = [{"nom": Value("nom")}]
    eq(get_json_value(check, "value_items"), [{"nom": {"name": "nom"}}])

    set_json_value(check, "value_items", [{"nom": {"name": "nom"}}])
    assert check.value_items is not nomnom, nomnom
    eq(check.value_items, [{"nom": Value("nom")}])

    check.value_items = [None]
    with assert_raises(ValueError, msg="expected dict with Value values, got None"):
        get_json_value(check, "value_items")

    with assert_raises(ValidationError, msg=(
        '["'
        "'value_items' field value has an invalid format: "
        "Cannot construct dict_of(Value) with 'bad' -> "
        "AttributeError: 'str' object has no attribute 'items'"
        '"]'
    )):
        set_json_value(check, "value_items", {"bad": "value"})


def test_jsonattrs_to_json():
    @unregistered_django_model
    class Check(models.Model):
        events = AttrsList(Event)

    check = Check(events=[Event()])
    eq(get_json_value(check, "events"), [{"day": "2022-07-19"}])


def test_jsonattrs_from_json():
    @unregistered_django_model
    class Check(models.Model):
        events = AttrsList(Event)

    check = Check()
    set_json_value(check, "events", [{"day": "2022-07-20"}])
    eq(check.events, [Event(day=date(2022, 7, 20))])


def test_value_to_string_returns_json_serializable():
    @unregistered_django_model
    class Check(models.Model):
        events = AttrsList(Event)

    check = Check(events=[Event()])
    eq(
        Check._meta.get_field("events").value_to_string(check),
        [{"day": "2022-07-19"}],
    )


def test_invalid_value_does_not_save():
    @unregistered_django_model
    class Check(models.Model):
        events = AttrsList(Event)

    check = Check(events=[{"monday": "2022-07-20"}])
    with assert_raises(NotAnAttrsClassError, msg=(
        "<class 'dict'> is not an attrs-decorated class."
    )):
        get_json_value(check, "events")


def get_json_value(model, field_name):
    """Get the JSON value of a field as it would be stored in the database

    Returns JSON that has been deserialized with `json.loads(value)`.
    """
    field = model._meta.get_field(field_name)
    value = field.pre_save(model, False)
    from django import VERSION as django_version
    if django_version[:2] >= (4, 2):
        # load as json obj to ensure it serializes properly
        return json.loads(json.dumps(field.get_prep_value(value)))
    else:
        return json.loads(field.get_prep_value(value))


def set_json_value(model, field_name, value):
    """Populate model with JSON data as if it were loaded from a database row

    `value` should be a Python data structure as if it had been read
    from the database and deserialized with `json.loads()`.
    """
    field = model._meta.get_field(field_name)
    py_value = field.from_db_value(json.dumps(value), None, None)
    setattr(model, field_name, py_value)


@define
class Point:
    x = field()
    y = field()


@define
class Value:
    name = field()


@define
class Event:
    day = field(factory=lambda: date(2022, 7, 19))

    def __jsonattrs_to_json__(self):
        data = asdict(self)
        data["day"] = data["day"].isoformat()
        return data

    @classmethod
    def __jsonattrs_from_json__(cls, data):
        data["day"] = date.fromisoformat(data["day"])
        return cls(**data)
