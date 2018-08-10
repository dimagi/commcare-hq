hqDefine('app_manager/js/summary/form_summary', function() {
    var assertProperties = hqImport("hqwebapp/js/assert_properties").assert,
        initialPageData = hqImport("hqwebapp/js/initial_page_data"),
        utils = hqImport('app_manager/js/summary/utils');

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

        self.showCalculations = ko.observable(false);
        self.toggleCalculations = function() {
            self.showCalculations(!self.showCalculations());
        };

        self.showRelevance = ko.observable(false);
        self.toggleRelevance = function() {
            self.showRelevance(!self.showRelevance());
        };

        self.showConstraints = ko.observable(false);
        self.toggleConstraints = function() {
            self.showConstraints(!self.showConstraints());
        };

        self.showDefaultValues = ko.observable(false);
        self.toggleDefaultValues = function() {
            self.showDefaultValues(!self.showDefaultValues());
        };

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
        self.questions = _.map(self.questions, function(question) {
            return questionModel(question);
        });

        self.isSelected = ko.observable(true);

        return self;
    };

    var questionModel = function(question) {
        var self = _.extend({
            options: [],
        }, question);

        var vellumType = initialPageData.get('VELLUM_TYPES')[question.type];
        self.icon = 'hq-icon ' + (vellumType ? vellumType.icon : '');

        return self;
    };

    $(function() {
        var menu = hqImport("app_manager/js/summary/menu"),
            lang = initialPageData.get('lang'),
            langs = initialPageData.get('langs');

        var formSummaryMenu = menu.menuModel({
            items: _.map(initialPageData.get("modules"), function(module) {
                return menu.menuItemModel({
                    id: module.id,
                    name: utils.translateName(module.name, lang, langs),
                    icon: utils.moduleIcon(module),
                    subitems: _.map(module.forms, function(form) {
                        return menu.menuItemModel({
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
