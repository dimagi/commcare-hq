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
                $(this).removeClass('btn-primary');
                $activeCheckbox.prop("checked", false);
            } else {
                $(this).addClass('btn-primary');
                $activeCheckbox.prop("checked", true);
            }
            $activeCheckbox.trigger('change');

            if ((!$el.children().hasClass('btn-primary')) && !canBeEmpty) {
                var $firstChild = $el.children().first();
                $firstChild.removeClass('btn-primary');
                $firstChild.addClass('btn-default');
                $firstChild.prop("checked", false)
                $('#' + $firstChild.data("checkfilter")).prop("checked", true);
                if ($(this).data("checkfilter") !== $firstChild.data("checkfilter")) {
                    $firstChild.removeClass('btn-default');
                    $firstChild.addClass('btn-primary');
                    $firstChild.prop("checked", true)
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
