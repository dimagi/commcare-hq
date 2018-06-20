hqDefine("accounting/js/enterprise_dashboard", [
    'jquery',
], function(
    $
) {
    $(function() {
        $("#hq-content .panel [data-url]").each(function() {
            var $element = $(this);
            $.ajax({
                url: $element.data("url"),
                success: function(data) {
                    $element.html(Number(data.total).toLocaleString());
                },
            });
        });
    });
});
