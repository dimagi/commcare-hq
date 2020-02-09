hqDefine('data_management/js/data_management', [
    'jquery',
    'jquery-ui/ui/datepicker',
], function ($) {
    'use strict';
    $(function () {
        $('.date-picker').datepicker({
            dateFormat: "yy-mm-dd",
            maxDate: 0
        });
    });
});
