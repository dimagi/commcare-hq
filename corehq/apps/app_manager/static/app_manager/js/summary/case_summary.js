hqDefine('app_manager/js/summary/case_summary', function() {
    $(function() {
        var initialPageData = hqImport("hqwebapp/js/initial_page_data"),
            menu = hqImport("app_manager/js/summary/menu");

        var caseSummaryMenu = menu.menuModel({
            items: _.map(initialPageData.get("case_metadata").case_types, function(case_type) {
                return menu.menuItemModel({
                    id: case_type.name,
                    name: case_type.name,
                    icon: "fcc fcc-fd-external-case appnav-primary-icon",
                    subitems: [],
                });
            }),
            viewAllItems: gettext("View All Cases"),
        });

        $("#hq-sidebar > nav").koApplyBindings(caseSummaryMenu);
    });
});
