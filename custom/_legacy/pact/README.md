# Pact Documentation

This is just some high-level pointers about the custom pact workflows.

## DOTs Processing

There is some good information on how the dots processing works on the mobile here: https://confluence.dimagi.com/display/pactsbir/Technical+Specifications.

On the HQ side this is mostly handled by the `process_dots_submission` function in `signals.py`.

Roughly what happens during a submissions is:

1. If a form is a DOTS form it is queued up for post-processing
2. This entails:
  1. Finding the relevant case.
  2. Running some calculations to get the latest DOTS data (`get_dots_case_json`).
  3. Submitting a *second* form that submits the DOTS data as a JSON case property. This should mirror the format of the confluence page above.


## CHW Schedules

Schedules are managed with a mapping of a user ID to a set of days.
You can view the schedule UI by going to "DOT Patient List" --> Search for a patient --> click on "profile" --> click on "schedule" tab.
This should take you to a page like this: https://www.commcarehq.org/a/pact/reports/custom/patient/?patient_id=66a4f2d0e9d5467e34122514c341ed92&view=schedule.
You can fill in a user for each day of the week and click "save" to save the schedule.

Behind the scenes what this does is appends the latest schedule to the `computed_` property on the case.
In particular it sets `case.computed_[PACT_SCHEDULES_NAMESPACE]` to a data structure that looks like:

```
{
    "pact_weekly_schedule": [
        {
            "comment": "",
            "doc_type": "CDotWeeklySchedule",
            "edited_by": null,
            "monday": "cs783",
            "started": "2014-10-17T18:29:09Z",
            "deprecated": false,
            "tuesday": "cs783",
            "friday": "cs783",
            "wednesday": "cs783",
            "thursday": "cs783",
            "sunday": null,
            "ended": "2014-10-17T18:29:12Z",
            "schedule_id": "f85d4686ede443ca99711cd114c49040",
            "created_by": "rachel@pact.commcarehq.org",
            "saturday": null
        },
        {
            "comment": "",
            "doc_type": "CDotWeeklySchedule",
            "edited_by": null,
            "monday": "cs783",
            "started": "2014-10-17T18:29:13Z",
            "deprecated": false,
            "tuesday": "cs783",
            "friday": "cs783",
            "wednesday": "cs783",
            "thursday": "cs783",
            "sunday": null,
            "ended": "2014-10-17T18:39:42Z",
            "schedule_id": "7654a0ba8ae245c784a8322a2d703cd0",
            "created_by": "rachel@pact.commcarehq.org",
            "saturday": null
        }
    ]
}
```

In addition to this a series of case properties named `dotSchedule[day]` e.g. `dotSchedulemonday` and `dotScheduletuesday` are set on the case that represent the *current* schedule.
This is accomplished by manually setting them when updated in `set_schedule_case_properties` as well as running a daily job to set them on all cases (if changed).
See `tasks.py` for more information on this.
