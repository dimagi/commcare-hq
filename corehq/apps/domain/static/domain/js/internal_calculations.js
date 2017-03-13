/* globals hqDefine */
hqDefine("domain/js/internal_calculations.js", function() {
    function load_calculation($calc_group) {
        var $calc_btn = $calc_group.find('.load-calc-btn');
        var $calc_error = $calc_group.find('.calc-error');
        var calc_tag = $calc_btn.attr('data-calc-tag');

        $calc_btn.html('Loading...');
        $.get(hqImport('hqwebapp/js/urllib.js').reverse('calculated_properties'), {calc_tag: calc_tag}, function(data) {
            if (!data.error) {
                $('#calc-' + calc_tag).html(data.value);
                $calc_btn.addClass('btn-success');
                $calc_error.html("");
            }
            else {
                $calc_btn.addClass('btn-danger');
                $calc_error.html(data.error);
            }
            $calc_btn.html('Reload Data').removeClass('btn-info');
        });
    }

    $(function() {
        $(document).on("click", ".load-calc-btn", function() {
            load_calculation($(this).parent());
        });
    
        $(document).on("click", '#load-all-btn', function() {
            $('.calc-group').each(function(_, ele) {
                load_calculation($(ele));
            });
        })
    });
});
