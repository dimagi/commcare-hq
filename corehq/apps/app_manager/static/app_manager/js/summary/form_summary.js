hqDefine('app_manager/js/summary/form_summary', function() {
    var assertProperties = hqImport("hqwebapp/js/assert_properties").assert,
        utils = hqImport('app_manager/js/summary/utils');

    var menuModel = function(options) {
        assertProperties(options, ['items', 'viewAllItems'], []);

        var self = {};

        self.items = options.items;
        self.viewAllItems = options.viewAllItems;

        self.selected = ko.observable();
        self.viewAllSelected = ko.computed(function() {
            return !self.selected();
        });

        return self;
    };

    $(function() {
        var initialPageData = hqImport("hqwebapp/js/initial_page_data"),
            lang = initialPageData.get('lang'),
            langs = initialPageData.get('langs');
        $("#hq-sidebar > nav").koApplyBindings(menuModel({
            items: _.map(initialPageData.get("modules"), function(module) {
                return {
                    id: module.id,
                    name: utils.translateName(module.name, lang, langs),
                    icon: utils.moduleIcon(module),
                    subitems: _.map(module.forms, function(form) {
                        return {
                            id: form.id,
                            name: utils.translateName(form.name, lang, langs),
                            icon: utils.formIcon(form),
                        };
                    }),
                };
            }),
            viewAllItems: gettext("View All Forms"),
        }));
    });
});
