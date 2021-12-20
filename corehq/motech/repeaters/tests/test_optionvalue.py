import attr
from testil import assert_raises, eq

from ..models import OptionValue


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


@attr.s
class FoodOptions:
    options = attr.ib(factory=dict)
    dish = OptionValue()
    food_option = OptionValue(default="veg", choices=["veg", "non-veg"])
    condiments = OptionValue(default=list)
