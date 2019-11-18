/**
 * This is used to initialize the buttongroup filters.
 * See the user filter for sample usage.
 */
hqDefine("reports/js/filters/button_group", ['jquery'], function ($) {
    var link = function (groupIdOrEl) {
        var $el = typeof groupIdOrEl === "string" ? $("#" + groupIdOrEl) : $(groupIdOrEl);
        $el.find("button").click(function (e) {
            e.preventDefault();
            var $activeCheckbox = $('#' + $(this).data("checkfilter"));

            if ($(this).hasClass('active')) {
                $(this).removeClass('active');
                $(this).addClass('btn-default');
                $activeCheckbox.prop("checked", false);
            } else {
                $(this).removeClass('btn-default');
                $(this).addClass('active');
                $activeCheckbox.prop("checked", true);
            }
            $activeCheckbox.trigger('change');

        });
    };

    return {
        link: link,
    };
});
