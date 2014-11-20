var filter_id = "#{{ filter.css_id }}-input";
$(filter_id).createDefaultDateRangePicker();
$(filter_id).on('apply', function(ev, picker) {
    var separator = $().getDateRangeSeparator();
    var dates = $(this).val().split(separator);
    $('#{{ filter.css_id }}-start').val(dates[0]);
    $('#{{ filter.css_id }}-end').val(dates[1]);
});
