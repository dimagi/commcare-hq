/**
 * This is used to initialize the buttongroup filters.
 * See the user filter for sample usage.
 */
hqDefine("reports/js/filters/button_group", ['jquery'], function ($) {
    var link = function (groupIdOrEl, canBeEmpty) {
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

            if ((!$el.children().hasClass('btn-primary')) && !canBeEmpty) {
                var $firstChild = $el.children().first();
                $firstChild.addClass('btn-primary');
                $('#' + $firstChild.data("checkfilter")).prop("checked", true);
                if ($(this).data("checkfilter") !== $firstChild.data("checkfilter")) {
                    $firstChild.removeClass('active');
                } else {
                    return false;
                }
            }
        });
    };

    return {
        link: link,
    };
});
