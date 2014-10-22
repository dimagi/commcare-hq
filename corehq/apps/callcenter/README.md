# Call Center / Supervisor statistics

This Django app comprises the majority of the code related to the 'supervisor app' feature.

This feature allows supervisors to view performance related statistics about mobile field workers
as part of a CommCare application.

This is accomplished as follows:

1. A case is created for each mobile user in a domain (the case type is configured by the user
   under project settings).
2. A fixture is generated that contains indicators for each mobile user and links them to the user's
   case (by using the case id).

With these two pieces in place it is possible to build an app in CommCare that will list all the
mobile worker cases and show the indicators for each one.

See https://help.commcarehq.or/display/commcarepublic/How+to+set+up+a+Supervisor-Call+Center+Application
    for user docs.

## Fixture format
    <fixture id="indicators:call-center" user_id="...">
        <indicators>
            <case id="user_case1">
                <indicator_a>1</indicator_a>
                <indicator_b>2</indicator_2>
            </case>
        </indicators>
    </fixture>

## Date ranges

Assume all dates are at 00h00.00.

| Date Range    | Description                       | Lower Bound (Inclusive)   | Upper Bound (Exclusive)   |
|---------------|-----------------------------------|---------------------------|---------------------------|
| Week0         | The last 7 days                   | (today-7)                 | today                     |
| Week1         | The last 7 days prior to week0    | (today-14)                | (today-8)                 |
| Month0        | The last 30 days                  | (today-30)                | today                     |
| Month1        | The last 30 days prior to Month0  | (today-60)                | (today-31)                |


## Indicators
### Forms Submitted
**Name**: forms_submitted_{period_name}

**Definition**: count of the number of forms submitted by each mobile worker during the time period

### Total Cases
**Name**: cases_total_{period_name} e.g. cases_total_week1

**Definition**: count of (case_created <= end_date and (case_closed >= start_date or case_not_closed).

Include cases that are owned by mobile worker or cases that are owned by a case owner group that the
mobile worker is part of.

### Total Cases By Case Type
This should be calculated for all known case types in the project, which includes any cases
from form submissions and any cases types defined in the projects applications.

**Name**: cases_total_{case_type}_{period_name} e.g. cases_total_mother_week0

**Definition**: Same as cases_total, but restrict the cases by case type.

### Opened Cases
**Name**: cases_opened_{period_name}

**Definition**: count of (case_opened >= start_date and case_opened <= end_date).

Include cases opened by the mobile worker.

### Opened Cases By Case Type
Similar to total cases by case type, this should be calculated for all known case types in the project.

**Name**: cases_opened_{case_type}_{period_name}

**Definition**:  Same as cases_opened, but restrict the cases by case type.

### Closed Cases
**Name**: cases_closed_{period_name}

**Definition**:  count of (case_closed >= start_date and case_closed <= end_date).

Include cases closed by the mobile worker.

### Closed Cases By Case Type
Similar to total cases by case type, this should be calculated for all known case types in the project.

**Name**: cases_closed_{case_type}_{period_name}

**Definition**:  Same as cases_closed, but restrict the cases by case type.

### Active Cases
**Naming**: cases_active_{period_name}

**Definition**:  count of cases where a case modification occurred between the start and end dates of the period (inclusive).  Include cases that are owned by mobile worker or cases that are owned by a case owner group that the mobile worker is part of.

### Active Cases By Case Type
Similar to total cases by case type, this should be calculated for all known case types in the project.

**Name**: cases_active_{case_type}_{period_name}

**Definition**:  Same as cases_active, but restrict the cases by case type.

## User assignment
When a fixture is generated for a supervisor it should only include data for users who are 'assigned' to the
supervisor. A user may be assigned to a supervisor in one of two ways:

1. The user's case is owned by the supervisor.
2. The user's case is owned by a case sharing group which the supervisor is part of.

## Caching
Since the indicators only include data up until midnight of the previous day the indicator values will
not change until the following midnight and should therefore be cached to avoid having to regenerate them
for each request.

The indicators for a specific user are cached in Django's default cache as JSON object and set to expire
at midnight of the current day.

## Timezones
All dates are adjusted to refer to the default timezone of the domain.

## Legacy indicators
In order to provide backwards compatibility for existing applications the following indicators are
also included in the fixture output:

* formsSubmitted{period_name} - the same values as forms_submitted_{period_name}
* casesUpdated{period_name} - the same values as cases_active_{period_name}
* totalCases - the total number of open cases at time of generation where case.user_id = mobile_user.user_id
