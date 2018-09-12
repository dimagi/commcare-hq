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
                $(this).addClass('btn-success');
                $activeCheckbox.prop("checked", true);
            } else {
                $(this).removeClass('btn-success');
                $activeCheckbox.prop("checked", false);
            }
            $activeCheckbox.trigger('change');

            if ((!$el.children().hasClass('btn-success')) && !canBeEmpty) {
                var $firstChild = $el.children().first();
                $firstChild.addClass('btn-success');
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
