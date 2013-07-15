function chevron_toggle(show, $toggling, $chevron, $holds_toggle_state, after_fn) {
    var chev = "icon-double-angle-";
    if (show) {
        $toggling.hide();
        $chevron.removeClass(chev + "down").addClass(chev + "right");
        $holds_toggle_state.data("show", false);
    } else {
        $toggling.show();
        $chevron.removeClass(chev + "right").addClass(chev + "down");
        $holds_toggle_state.data("show", true);
    }
    if (after_fn) {
        after_fn();
    }
}

$(function () {
    $(".more-sortable-button").click(function() {
        var $this = $(this);
        var sortable = $this.data('sortable').replace(new RegExp("\\.", "g"), "\\.");
        $('.sortable-' + sortable).show();
        $this.hide();
        return false;
    });

    $(".facet-group-btn").click(function(){
        var $this = $(this);
        var group_name = $this.data('name');
        var $facet_group = $(".facet-group[data-group-name='" + group_name + "']");

        chevron_toggle($facet_group.data('show'), $facet_group, $this.children('.facet-group-chevron'), $facet_group);
        return false;
    });

    $(".facet-btn").click(function(){
        var $this = $(this);
        var sortable = $this.data('sortable').replace(".", "\\.");

        var fn = function() {
            $(".more-sortable-button[data-sortable='" + sortable + "']").hide();
        };

        chevron_toggle($this.data('show'), $(".sortable-" + sortable), $this.find('.facet-chevron'), $this, fn);
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