hqDefine('app_manager/js/summary/form_summary', function() {
    var assertProperties = hqImport("hqwebapp/js/assert_properties").assert,
        utils = hqImport('app_manager/js/summary/utils');

    var menuItemModel = function(options) {
        assertProperties(options, ['id', 'name', 'icon'], ['subitems']);
        var self = _.extend({}, options);

        self.isSelected = ko.observable(false);
        self.select = function() {
            self.isSelected(true);
        };

        return self;
    };

    var menuModel = function(options) {
        assertProperties(options, ['items', 'viewAllItems'], []);

        var self = {};

        self.items = options.items;
        self.viewAllItems = options.viewAllItems;

        self.selectedItemId = ko.observable('');      // blank indicates "View All"
        self.viewAllSelected = ko.computed(function() {
            return !self.selectedItemId();
        });

        self.select = function(item) {
            self.selectedItemId(item.id);
            _.each(self.items, function(i) {
                i.isSelected(item.id === i.id);
                _.each(i.subitems, function(s) {
                    s.isSelected(item.id === s.id);
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

        self.selectedItemId = ko.observable('');      // blank indicates "View All"
        self.selectedItemId.subscribe(function(selectedId) {
            _.each(self.modules, function(module) {
                module.isSelected(!selectedId || selectedId === module.id || _.find(module.forms, function(f) { return selectedId === f.id }));
                _.each(module.forms, function(form) {
                    form.isSelected(!selectedId || selectedId === form.id || selectedId === module.id);
                });
            });
        });

        return self;
    };

    var moduleModel = function(module, lang, langs) {
        var self = _.extend({}, module);

        self.name = utils.translateName(self.name, lang, langs);
        self.url = hqImport("hqwebapp/js/initial_page_data").reverse("view_module", self.id);
        self.icon = utils.moduleIcon(self) + ' hq-icon';
        self.forms = _.map(self.forms, function(form) {
            return formModel(form, lang, langs);
        });

        self.isSelected = ko.observable(true);

        return self;
    };

    var formModel = function(form, lang, langs) {
        var self = _.extend({}, form);

        self.name = utils.translateName(self.name, lang, langs);
        self.url = hqImport("hqwebapp/js/initial_page_data").reverse("form_source", self.id);
        self.icon = utils.formIcon(self) + ' hq-icon';

        self.isSelected = ko.observable(true);

        return self;
    };

    $(function() {
        var initialPageData = hqImport("hqwebapp/js/initial_page_data"),
            lang = initialPageData.get('lang'),
            langs = initialPageData.get('langs');

        var formSummaryMenu = menuModel({
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
        });

        var formSummaryContent = contentModel({
            lang: lang,
            langs: langs,
            modules: initialPageData.get("modules"),
        });

        $("#hq-sidebar > nav").koApplyBindings(formSummaryMenu);
        $("#js-appmanager-body").koApplyBindings(formSummaryContent);

        formSummaryMenu.selectedItemId.subscribe(function(newValue) {
            formSummaryContent.selectedItemId(newValue);
        });
    });
});
