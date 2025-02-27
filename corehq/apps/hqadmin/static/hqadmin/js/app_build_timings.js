hqDefine('hqadmin/js/app_build_timings', [
    "jquery",
    "jquery-treetable/jquery.treetable",
    "commcarehq",
], function ($) {
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
});
