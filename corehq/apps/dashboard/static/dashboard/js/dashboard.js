hqDefine("dashboard/js/dashboard", function() {
    $(function() {
        // Set up popovers
        // TODO: need to initialize these every time there's a new page (report titles have popovers)
        $(".panel-dashboard [data-popover]").each(function() {
            var $target = $(this),
                data = $target.data();
            $target.popover({
                title: data.popoverTitle,
                content: data.popover,
                placement: data.popoverPlacement || "top",
                trigger: 'hover',
            });
        });

        // TODO: Initial fetch for paginated tiles
    });
});
