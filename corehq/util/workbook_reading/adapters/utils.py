import ast
import datetime

from dimagi.utils.parsing import string_to_boolean, string_to_datetime


def format_str_to_its_type(str_value):
    """Attempt to format a str_value into its type."""
    # Try to see if the str_value is a empty.
    if str_value == "":
        return None

    # Try to see if the str_value is a number (float or integer).
    try:
        number = ast.literal_eval(str_value)
        if int(number) == float(number):
            return int(number)
        else:
            return float(number)
    except (SyntaxError, ValueError, TypeError):
        pass

    # Try to see if the str_value is a date or a time.
    try:
        parsed_datetime = string_to_datetime(str_value)
        # Because dateutil.parser.parse always returns a datetime, we do some guessing
        # for whether the value is a datetime, a date, or a time.
        today_midnight = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_date = today_midnight.date()
        # If the parsed_datetime time is midnight, then check if the user indicated
        # midnight or not.
        if parsed_datetime.time() == today_midnight.time():
            if ("am" in str_value.lower() or "00:00" in str_value):
                # The user has indicated to use midnight.
                # If the str_value is long, then this must be a datetime.
                if len(str_value) > 10:
                    return parsed_datetime
                else:
                    # The str_value is short, so this must be a time.
                    return parsed_datetime.time()
            else:
                # The user has not indicated to use midnight, so this must be a date.
                return parsed_datetime.date()
        elif parsed_datetime.date() == today_date:
            # We have already handled the case that the user specified a date (but
            # not a time), so parsed_datetime is a datetime with a time of midnight.
            # If the parsed_datetime has a date of today, but a time of not midnight,
            # then either the user specified both the date and the time (meaning
            # we should return the datetime), or the user specified only the time (so
            # we should return only the time).

            # If the str_value is long, then this must be a datetime.
            if len(str_value) > 10:
                return parsed_datetime
            else:
                # The str_value is short, so this must be a time.
                return parsed_datetime.time()
        else:
            # Otherwise, this must be a datetime.
            return parsed_datetime
    except ValueError:
        pass

    # Try to see if the str_value is a boolean.
    try:
        return string_to_boolean(str_value)
    except ValueError:
        pass

    # Try to see if the str_value is a percent.
    if "%" in str_value:
        try:
            # return float(str_value.replace("%", "")) / 100

            str_without_sign = str_value.replace("%", "")
            num_decimal_places = 2
            if "." in str_without_sign:
                num_decimal_places = len(str_without_sign.split(".")[-1]) + 2
            return round(float(str_without_sign) / 100, num_decimal_places)

        except ValueError:
            pass

    return str_value
