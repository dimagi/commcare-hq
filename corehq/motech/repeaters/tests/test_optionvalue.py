import attr
from testil import assert_raises, eq

from corehq.motech.repeaters.optionvalue import OptionSchema, OptionValue


def test_basic_option_value():
    order = FoodOptions()
    order.dish = "Chicken"
    eq(order.dish, "Chicken")
    eq(order.options, {"dish": "Chicken"})


def test_option_value_not_set():
    order = FoodOptions()
    with assert_raises(AttributeError):
        order.option
    eq(order.options, {})


def test_default_option_value():
    order = FoodOptions()
    eq(order.food_option, 'veg')
    eq(order.options, {
        'food_option': 'veg'
    })


def test_setting_value_in_default_option_value():
    order = FoodOptions()
    order.food_option = "non-veg"
    eq(order.options, {
        'food_option': 'non-veg',
    })


def test_raises_on_invalid_choice():
    order = FoodOptions()
    with assert_raises(ValueError):
        order.food_option = "vegan"
    eq(order.options, {})


def test_instance_of_optionvalue():
    assert isinstance(FoodOptions.dish, OptionValue), repr(FoodOptions.dish)


def test_option_with_callable_default():
    order = FoodOptions()
    order.condiments.append("ketchup")
    eq(order.options, {'condiments': ["ketchup"]})


def test_schema_passed_in_option():
    order = FoodOptions()
    order.packaged_water = WaterBottle({"qty": 2})
    eq(order.options["packaged_water"], {"qty": 2})


def test_schema_default_value():
    order = FoodOptions()
    eq(order.packaged_water, WaterBottle({}))
    eq(order.packaged_water.qty, "1")
    eq(order.packaged_water, WaterBottle({"qty": "1"}))


def test_schema_with_default():
    with assert_raises(ValueError):
        OptionValue(schema=WaterBottle, default={})


def test_schema_value_equality():
    order = FoodOptions()
    order.packaged_water = WaterBottle({"qty": 2})
    water = order.packaged_water
    eq(water.qty, 2)
    water.qty = 3
    eq(order.packaged_water.qty, 3)
    eq(order.packaged_water, water)


def test_raises_on_invalid_schema():
    order = FoodOptions()
    with assert_raises(TypeError):
        order.packaged_water = {"somedict": "hola"}


class WaterBottle(OptionSchema):
    qty = OptionValue(default="1")


@attr.s
class FoodOptions:
    options = attr.ib(factory=dict)
    dish = OptionValue()
    food_option = OptionValue(default="veg", choices=["veg", "non-veg"])
    condiments = OptionValue(default=list)
    packaged_water = OptionValue(schema=WaterBottle)
