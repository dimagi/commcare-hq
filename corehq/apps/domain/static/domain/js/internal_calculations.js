hqDefine("domain/js/internal_calculations", [
    'jquery',
    'hqwebapp/js/initial_page_data',
], function (
    $,
    initialPageData
) {
    function loadCalculation($group) {
        var $btn = $group.find('.load-calc-btn');
        var $error = $group.find('.calc-error');
        var tag = $btn.attr('data-calc-tag');

        $btn.html('Loading...');
        $.get(initialPageData.reverse('calculated_properties'), {calc_tag: tag}, function (data) {
            if (!data.error) {
                $('#calc-' + tag).html(data.value);
                $btn.addClass('btn-default');
                $error.html("");
            } else {
                $btn.addClass('btn-danger');
                $error.html(data.error);
            }
            $btn.html('Reload Data').removeClass('btn-primary');
        });
    }

    $(function () {
        $(document).on("click", ".load-calc-btn", function () {
            loadCalculation($(this).parent());
        });

        $(document).on("click", '#load-all-btn', function () {
            $('.calc-group').each(function (_, ele) {
                loadCalculation($(ele));
            });
        });
    });
});
