hqDefine("case/js/case_hierarchy", [
    'jquery',
    'jquery-treetable/jquery.treetable',
], function (
    $,
) {
    $(function () {
        var tree = $("#related_cases").treetable({
            expandable: true,
            initialState: "expanded",
        });

        $(".case-closed").each(function () {
            tree.treetable('collapseNode', ($(this).data('tt-id')));
        });
    });
});
