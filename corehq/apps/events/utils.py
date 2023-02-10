from corehq.apps.es.case_search import wrap_case_search_hit


def wrap_es_case_as_event(case):
    from corehq.apps.events.models import Event

    # Convert to CommCareCase
    case_ = wrap_case_search_hit(case)
    program_manager = None  # probably the case owner?

    return Event(
        domain=case_.domain,
        name=case_.name,
        start=case_.get_case_property('start'),
        end=case_.get_case_property('end'),
        attendance_target=case_.get_case_property('attendance_target'),
        sameday_reg=case_.get_case_property('sameday_reg'),
        track_each_day=case_.get_case_property('track_each_day'),
        case=case_,
        is_open=case.get_case_property('is_open'),
        attendee_list_status=case_.get_case_property('attendee_list_status'),
        program_manager=program_manager,
    )
