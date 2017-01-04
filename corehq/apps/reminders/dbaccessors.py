

def get_schedule_instances_for_schedule_and_recipient(schedule_id, recipient_type, recipient_id):
    from corehq.apps.reminders.models import ScheduleInstance
    return ScheduleInstance.objects.filter(
        schedule_id=schedule_id,
        recipient_type=recipient_type,
        recipient_id=recipient_id
    )


def save_schedule_instance(instance):
    instance.save()
