MOTECH Repeaters
================

See the [MOTECH README](../README.md#repeaters) for a brief introduction to repeaters.


How Do They Work?
-----------------

A good place to start is [signals.py](./signals.py). From the bottom of the file you can see that a repeat record is created when a form is received, or after a case or user or location is saved.

The `create_repeat_records()` function will iterate through the [`Repeater`](./models.py) instances of a given class type that are configured for the domain. For example, after a case has been saved, `create_repeat_records()` is called with `CaseRepeater`, then `CreateCaseRepeater` and then `UpdateCaseRepeater`. A domain can have many CaseRepeaters configured to forward case changes to different URLs (or the same URL with different credentials). The `register()` method of each of the domain's CaseRepeaters will be called with the case as its payload.

The same applies to forms that are received, or users or locations that are saved.

The `register()` method creates a `RepeatRecord` instance, and associates it with the payload using the payload's ID. The RepeatRecord's `next_check` property is set to `datetime.utcnow()`.

Next we jump to [tasks.py](./tasks.py). The `check_repeaters()` function will run every `CHECK_REPEATERS_INTERVAL` (currently set to 5 minutes). Each RepeatRecord due to be processed will be added to the CELERY_REPEAT_RECORD_QUEUE.

When it is pulled off the queue and processed, if its Repeater is paused it will be postponed. If its Repeater is deleted it will be deleted. And if it's waiting to be sent, or resent, its `fire()` method will be called ... which will call its Repeater's `fire_for_record()` method.

The Repeater will transform the payload into the right format for the Repeater's class type and configuration, and then send the transformed data to the Repeater's destination URL.

The response from the destination will be handled according to whether the request succeeded, failed, or raised an exception. It will create a RepeatRecordAttempt, and may include other actions depending on the class of Repeater.

RepeatRecordAttempts are listed under Data Forwarding Records.
