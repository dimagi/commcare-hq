var linkButtonGroup = function (groupId) {
    // this is used to initialize the buttongroup filters
    // see the user filter for sample usage.
    var jqGroupId = "#" + groupId;
    $(jqGroupId + " button").click(function(e) {
        e.preventDefault();
        var $activeCheckbox = $('#'+$(this).data("checkfilter"));
	
        if($(this).hasClass('active')) {
            $(this).addClass('btn-success');
            $activeCheckbox.attr("checked", true);
        } else {
            $(this).removeClass('btn-success');
            $activeCheckbox.attr("checked", false);
        }

        if(!$(jqGroupId).children().hasClass('btn-success')) {
            var $firstChild = $(jqGroupId).children().first();
            $firstChild.addClass('btn-success');
            $('#'+$firstChild.data("checkfilter")).attr("checked", true);
            if ($(this).data("checkfilter") != $firstChild.data("checkfilter")) {
                $firstChild.removeClass('active');
            } else {
                return false;
            }
        }
    });
};
