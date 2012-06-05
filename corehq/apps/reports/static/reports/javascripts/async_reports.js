$(function () {
    var $submitButton = $('#paramSelectorForm button[type="submit"]');
    $submitButton.addClass('disabled');
    $('#paramSelectorForm').change(function () {
        $submitButton.addClass('btn-primary');
    });

    updateFilters();
    updateReport();

    function updateFilters() {
        $.ajax({
            url: window.location.pathname.replace('/reports/', '/reports/async/filters/')+window.location.search,
            dataType: 'json',
            success: function(data) {
                $('#hq-report-filters').html(data.filters);
                $('#reportFiltersAccordion').removeClass('hide');
                $submitButton.removeClass('btn-primary');
            }
        });
    }
    function updateReport() {
        $.ajax({
            url: window.location.pathname.replace('/reports/', '/reports/async/')+window.location.search,
            dataType: 'json',
            success: function(data) {
                $('#report-content').html(data.report);
                $('.hq-report-time-notice').removeClass('hide');
                $submitButton.button('reset');
            },
            beforeSend: function () {
                $submitButton.button('loading');
            }
        });
    }

    $('#paramSelectorForm').submit(function (event) {
        var params = $(this).serialize();

        History.pushState(null,window.location.title,window.location.pathname+"?"+params);
        updateFilters();
        updateReport();
        return false;
    });


});