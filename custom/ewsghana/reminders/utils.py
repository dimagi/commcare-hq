def user_has_reporting_location(user):
    sql_location = user.sql_location
    if not sql_location:
        return False
    return not sql_location.location_type.administrative
