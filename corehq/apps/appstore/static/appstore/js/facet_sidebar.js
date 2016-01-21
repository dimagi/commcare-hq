function escapeRegExp(str) {
    return str.replace(/[\-\[\]\/\{\}\(\)\*\+\?\.\\\^\$\|]/g, "\\$&");
}

function replaceAll(find, replace, str) {
    // http://stackoverflow.com/questions/1144783/replacing-all-occurrences-of-a-string-in-javascript#answer-1144788
    return str.replace(new RegExp(escapeRegExp(find), 'g'), replace);
}

function chevron_toggle(show, $toggling, $chevron, $holds_toggle_state, after_fn) {
    var chev = "icon-double-angle-",
        chevB3 = "fa-angle-double-";
    if (show) {
        $toggling.hide();
        $chevron
            .removeClass(chev + "down")
            .addClass(chev + "right")
            .removeClass(chevB3 + "down")
            .addClass(chevB3 + "right");
        $holds_toggle_state.data("show", false);
    } else {
        $toggling.show();
        $toggling.removeClass('hide');
        $chevron
            .removeClass(chev + "right")
            .addClass(chev + "down")
            .removeClass(chevB3 + "right")
            .addClass(chevB3 + "down");
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
        $('.sortable-' + sortable).removeClass('hide');
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
        var sortable = replaceAll(".", "\\.", $this.data('sortable'));

        var fn = function() {
            $(".more-sortable-button[data-sortable='" + sortable + "']").hide();
        };

        chevron_toggle($this.data('show'), $(".sortable-" + sortable), $this.find('.facet-chevron'), $this, fn);
        return false;
    });

    var $update_btn = $("#update-facets");
    var $facet_search_form = $("#facet-search");
    var $facet_search_bar = $facet_search_form.find('input');
    $update_btn.click(function() {
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

        if ($facet_search_bar.val()) {
            var name = $facet_search_bar.attr("name") || "search";
            url += name + "=" + $facet_search_bar.val()
        }
        window.location = encodeURI(url);
    });

    $facet_search_form.submit(function(e) {
        e.preventDefault();
        $update_btn.click();
    });
});
