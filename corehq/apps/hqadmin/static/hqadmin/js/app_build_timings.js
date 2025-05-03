import "commcarehq";
import $ from "jquery";
import "jquery-treetable/jquery.treetable";

$(function () {
    $("#timingTable").treetable({
        expandable: true,
        expanderTemplate: '<i class="fa fa-angle-double-down" /> ',
        initialState: 'expanded',
        clickableNodeNames: true,
        onNodeExpand: function () {
            $(this.expander).addClass("fa-angle-double-down");
            $(this.expander).removeClass("fa-angle-double-right");
        },
        onNodeCollapse: function () {
            $(this.expander).removeClass("fa-angle-double-down");
            $(this.expander).addClass("fa-angle-double-right");
        },
    });
});
