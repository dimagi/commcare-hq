hqDefine("dashboard/js/dashboard", function() {
    $(function() {
        $(".panel-dashboard [data-popover]").each(function() {
            var $target = $(this),
                data = $target.data();
            $target.popover({
                title: data.popoverTitle,
                content: data.popover,
                placement: $target.closest(".panel-heading").length ? "bottom" : "top",
                trigger: 'hover',
            });
        });
    });
});
