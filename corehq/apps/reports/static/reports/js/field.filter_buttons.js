var linkButtonGroup = function (groupIdOrEl, can_be_empty) {
    // this is used to initialize the buttongroup filters
    // see the user filter for sample usage.
    var $el = typeof groupIdOrEl === "string" ? $("#" + groupIdOrEl) : $(groupIdOrEl);
    $el.find("button").click(function(e) {
        e.preventDefault();
        var $activeCheckbox = $('#'+$(this).data("checkfilter"));

        if($(this).hasClass('active')) {
            $(this).addClass('btn-success');
            $activeCheckbox.prop("checked", true);
        } else {
            $(this).removeClass('btn-success');
            $activeCheckbox.prop("checked", false);
        }
        $activeCheckbox.trigger('change');

        if((!$el.children().hasClass('btn-success')) && !can_be_empty) {
            var $firstChild = $el.children().first();
            $firstChild.addClass('btn-success');
            $('#'+$firstChild.data("checkfilter")).prop("checked", true);
            if ($(this).data("checkfilter") != $firstChild.data("checkfilter")) {
                $firstChild.removeClass('active');
            } else {
                return false;
            }
        }
    });
};
