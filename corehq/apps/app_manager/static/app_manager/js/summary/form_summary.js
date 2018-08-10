hqDefine('app_manager/js/summary/form_summary', function() {
    var assertProperties = hqImport("hqwebapp/js/assert_properties").assert,
        utils = hqImport('app_manager/js/summary/utils');

    var menuItemModel = function(options) {
        assertProperties(options, ['id', 'name', 'icon'], ['subitems']);
        var self = _.extend({}, options);

        self.selected = ko.observable(false);
        self.select = function() {
            self.selected(true);
        };

        return self;
    };

    var menuModel = function(options) {
        assertProperties(options, ['items', 'viewAllItems'], []);

        var self = {};

        self.items = options.items;
        self.viewAllItems = options.viewAllItems;

        self.selected = ko.observable('');
        self.viewAllSelected = ko.computed(function() {
            return !self.selected();
        });

        self.select = function(item) {
            self.selected(item.id);
            _.each(self.items, function(i) {
                i.selected(item.id === i.id);
                _.each(i.subitems, function(s) {
                    s.selected(item.id === s.id);
                });
            });
        };
        self.selectAll = function() {
            self.select('');
        };

        return self;
    };

    var contentModel = function(options) {
        assertProperties(options, ['lang', 'langs', 'modules'], []);

        var self = {};
        self.lang = options.lang;
        self.langs = options.langs;
        self.modules = _.map(options.modules, function(module) {
            return moduleModel(module, self.lang, self.langs);
        });

        return self;
    };

    var moduleModel = function(module, lang, langs) {
        var self = _.extend({}, module);

        self.name = utils.translateName(self.name, lang, langs);
        self.forms = _.map(self.forms, function(form) {
            form.name = utils.translateName(form.name, lang, langs);
            return form;
        });

        return self;
    };

    $(function() {
        var initialPageData = hqImport("hqwebapp/js/initial_page_data"),
            lang = initialPageData.get('lang'),
            langs = initialPageData.get('langs');

        $("#hq-sidebar > nav").koApplyBindings(menuModel({
            items: _.map(initialPageData.get("modules"), function(module) {
                return menuItemModel({
                    id: module.id,
                    name: utils.translateName(module.name, lang, langs),
                    icon: utils.moduleIcon(module),
                    subitems: _.map(module.forms, function(form) {
                        return menuItemModel({
                            id: form.id,
                            name: utils.translateName(form.name, lang, langs),
                            icon: utils.formIcon(form),
                        });
                    }),
                });
            }),
            viewAllItems: gettext("View All Forms"),
        }));

        $("#js-appmanager-body").koApplyBindings(contentModel({
            lang: lang,
            langs: langs,
            modules: initialPageData.get("modules"),
        }));
    });
});
