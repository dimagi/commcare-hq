$(function () {
    var $submitButton = $('#paramSelectorForm button[type="submit"]');
    $submitButton.addClass('disabled');
    $('#paramSelectorForm').change(function () {
        $submitButton.addClass('btn-primary');
    });

    updateReport(true, window.location.search.substr(1));

    function updateFilters(form_params) {
        $.ajax({
            url: window.location.pathname.replace('/reports/', '/reports/async/filters/')+"?"+form_params,
            dataType: 'json',
            success: loadFilters
        });
    }

    function loadFilters (data) {
        $('#hq-report-filters').html(data.filters);
        $('#reportFiltersAccordion').removeClass('hide');
        $submitButton.removeClass('btn-primary');
    }

    function updateReport(initial_load, params) {
        var process_filters = (initial_load) ? "hq_filters=true&": "";
        $.ajax({
            url: window.location.pathname.replace('/reports/', '/reports/async/')+"?"+process_filters+params,
            dataType: 'json',
            success: function(data) {
                if (data.filters)
                    loadFilters(data);
                $('#report-content').html(data.report);
                $('.hq-report-time-notice').removeClass('hide');
                $submitButton.button('reset');
            },
            beforeSend: function () {
                $submitButton.button('loading');
            }
        });
    }

    $('#paramSelectorForm').submit(function () {
        var params = $(this).serialize();
        History.pushState(null,window.location.title,window.location.pathname+"?"+params);
        updateFilters(params);
        updateReport(false, params);
        return false;
    });


});