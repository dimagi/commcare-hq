'use strict';
hqDefine("reports/js/bootstrap3/application_status", [
    "jquery",
], function (
    $
) {
    $(function () {
        $('#report-content').on('click', '.toggle-all-locations', function (e) {
            $(this).prevAll('.locations-list').toggle();
            $(this).children('span').toggle();
            $(this).prevAll('.all-locations-list').toggle();
            e.preventDefault();
        });
    });
});