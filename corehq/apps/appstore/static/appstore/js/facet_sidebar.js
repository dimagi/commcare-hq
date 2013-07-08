$(function () {
    $(".more-sortable-button").click(function() {
        var $this = $(this);
        var sortable = $this.data('sortable').replace(".", "\\.");
        $('.sortable-' + sortable).show();
        $this.hide();
        return false;
    });

    $("#update-facets").click(function() {
        var $this = $(this);
        var url = "?";
        if ($this.data('params')) {
            url += $(this).data('params') + "&";
        }
        var prefix = "";
        if ($this.data('prefix')) {
            prefix += $(this).data('prefix')
        }

        $(".sortable").each(function(){
            var sortable_name = $(this).data("name");
            $(this).find('.facet-checkbox').each(function(){
                $facet = $(this);
                if ($facet.is(":checked") && $facet.attr("name")) {
                    url += prefix + sortable_name + "=" + $facet.attr("name") + "&";
                }
            })
        });

        window.location = encodeURI(url);
    });
});