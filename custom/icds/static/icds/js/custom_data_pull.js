hqDefine('icds/js/custom_data_pull', [
    'jquery',
    'locations/js/search',
    'hqwebapp/js/widgets', // using select2/dist/js/select2.full.min for ko-select2 on location select
    'jquery-ui/ui/datepicker',
], function (
    $
) {
    'use strict';
    $(function () {
        $('#month_select').datepicker({
            dateFormat: "yy-mm-dd",
            beforeShowDay: function (date) {
                //getDate() returns the day (0-31)
                if (date.getDate() === 1) {
                    return [true, ''];
                }
                return [false, ''];
            },
        });
    });
});
