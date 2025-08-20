import $ from "jquery";
import _ from "underscore";
import initialPageData from "hqwebapp/js/initial_page_data";
import moment from "moment/moment";
import "bootstrap-daterangepicker/daterangepicker";
import "bootstrap-daterangepicker/daterangepicker.css";


/* TODO B5: Remove me after bootstrap5 migration, replaced by hqwebapp/js/tempus_dominus */
$.fn.getDateRangeSeparator = function () {
    return ' to ';
};
$.fn.createDateRangePicker = function (
    rangeLabels, separator, startdate, enddate,
) {
    var ranges = {};
    ranges[rangeLabels.last_7_days] = [
        moment().subtract('7', 'days').startOf('days'),
    ];

    ranges[rangeLabels.last_month] = [
        moment().subtract('1', 'months').startOf('month'),
        moment().subtract('1', 'months').endOf('month'),
    ];

    ranges[rangeLabels.last_30_days] = [
        moment().subtract('30', 'days').startOf('days'),
    ];
    var config = {
        showDropdowns: true,
        ranges: ranges,
        timePicker: false,
        locale: {
            format: 'YYYY-MM-DD',
            separator: separator,
        },
    };
    var hasStartAndEndDate = !_.isEmpty(startdate) && !_.isEmpty(enddate);
    if (hasStartAndEndDate) {
        config.startDate = new Date(startdate);
        config.endDate = new Date(enddate);
    }

    $(this).daterangepicker(config);

    // UCRs
    if (initialPageData.get('daterangepicker-show-clear')) {
        // Change 'Cancel' button text to 'Clear'
        var $el = $(this);
        config.locale.cancelLabel = gettext('Clear');
        $el.daterangepicker(config);

        // Add clearing functionality
        $el.on('cancel.daterangepicker', function () {
            $el.val(gettext("Show All Dates")).change();

            // Clear startdate and enddate filters
            var filterId = $(this)[0].getAttribute("name");
            var filterIdStart = filterId + "-start";
            var filterIdEnd = filterId + "-end";
            if (document.getElementById(filterIdStart) && document.getElementById(filterIdEnd)) {
                document.getElementById(filterIdStart).setAttribute("value", "");
                document.getElementById(filterIdEnd).setAttribute("value", "");
            }
        });
    }

    if (! hasStartAndEndDate) {
        $(this).val("");
    }
};
$.fn.createBootstrap3DefaultDateRangePicker = function () {
    this.createDateRangePicker(
        {
            last_7_days: 'Last 7 Days',
            last_month: 'Last Month',
            last_30_days: 'Last 30 Days',
        },
        this.getDateRangeSeparator(),
    );
};
