def format_datespan_by_case_status(datespan, status):
    datespan = copy.copy(datespan) # copy datespan
    common_kwargs = dict(
        format=datespan.format,
        inclusive=datespan.inclusive,
        timezone=datespan.timezone
    )
    if status == 'opened_on':
        datespan = DateSpan(
            None,
            datespan.enddate,
            **common_kwargs
        )
    elif status == "closed_on":
        datespan = DateSpan(
            datespan.startdate,
            None,
            **common_kwargs
        )
    return datespan