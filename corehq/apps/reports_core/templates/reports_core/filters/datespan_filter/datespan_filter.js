(function ($, gettext) {
    var filter_id = "#{{ filter.css_id }}-input";
    var filter_id_start = '#{{ filter.css_id }}-start';
    var filter_id_end = '#{{ filter.css_id }}-end';

    $(filter_id).createBootstrap3DefaultDateRangePicker();
    $(filter_id).on('apply change', function (ev, picker) {
        var separator = $().getDateRangeSeparator();
        var dates = $(this).val().split(separator);
        $(filter_id_start).val(dates[0]);
        $(filter_id_end).val(dates[1]);
    });

    if (!$(filter_id).val() && $(filter_id_start).val() && $(filter_id_end).val()) {
        var text = $(filter_id_start).val() + $().getDateRangeSeparator() + $(filter_id_end).val();
        $(filter_id).val(text);
    } else if (!$(filter_id).val()) {
        $(filter_id).val(gettext("Show All Dates"));
    }
})($, gettext);
