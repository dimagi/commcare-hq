var linkButtonGroup = function (groupId, can_be_empty) {
    // this is used to initialize the buttongroup filters
    // see the user filter for sample usage.
    var jqGroupId = "#" + groupId;
    $(jqGroupId + " button").click(function(e) {
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

        if((!$(jqGroupId).children().hasClass('btn-success')) && !can_be_empty) {
            var $firstChild = $(jqGroupId).children().first();
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
