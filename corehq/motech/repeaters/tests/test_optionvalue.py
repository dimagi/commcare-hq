from datetime import datetime
import doctest

import attr
from testil import assert_raises, eq

from corehq.motech.repeaters.optionvalue import DateTimeCoder, OptionValue
from dimagi.utils.parsing import json_format_datetime


def test_basic_option_value():
    order = FoodOptions()
    order.dish = "Chicken"
    eq(order.dish, "Chicken")
    eq(order.options, {"dish": "Chicken"})


def test_get_default_value():
    eq(FoodOptions.food_option.get_default_value(), 'veg')


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


def test_datetime_coder_with_datetime():
    order = FoodOptions()
    ordered_on = datetime.now()
    order.ordered_on = ordered_on
    eq(order.options['ordered_on'], json_format_datetime(ordered_on))


def test_datetime_coder_with_str_datetime():
    order = FoodOptions()
    ordered_on = json_format_datetime(datetime.now())
    order.ordered_on = ordered_on
    eq(order.options['ordered_on'], ordered_on)


def test_datetime_coder_with_invalid_str():
    order = FoodOptions()
    with assert_raises(ValueError):
        order.ordered_on = 'blah_blah'


def test_instance_of_optionvalue():
    assert isinstance(FoodOptions.dish, OptionValue), repr(FoodOptions.dish)


def test_option_with_callable_default():
    order = FoodOptions()
    order.condiments.append("ketchup")
    eq(order.options, {'condiments': ["ketchup"]})


def test_raises_on_no_options():
    order = BadFoodOptions()
    with assert_raises(AssertionError):
        order.dish = 'Rhino'


def test_raises_on_bad_options_type():
    order = AlsoBadFoodOptions()
    with assert_raises(AssertionError):
        order.dish = 'Albatross'


def test_doctests():
    import corehq.motech.repeaters.optionvalue
    results = doctest.testmod(corehq.motech.repeaters.optionvalue)
    assert results.failed == 0


@attr.s
class FoodOptions:
    options = attr.ib(factory=dict)
    dish = OptionValue()
    food_option = OptionValue(default="veg", choices=["veg", "non-veg"])
    condiments = OptionValue(default=list)
    ordered_on = OptionValue(coder=DateTimeCoder)


class BadFoodOptions:
    dish = OptionValue()


class AlsoBadFoodOptions:
    options = (
        ('ALB', 'Albatross'),
        ('BON', 'Bonobo'),
        ('DOL', 'Dolphin'),
    )
    dish = OptionValue()
