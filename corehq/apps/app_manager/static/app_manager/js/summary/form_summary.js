hqDefine('app_manager/js/summary/form_summary', function() {
    var assertProperties = hqImport("hqwebapp/js/assert_properties").assert,
        initialPageData = hqImport("hqwebapp/js/initial_page_data"),
        utils = hqImport('app_manager/js/summary/utils');

    var contentModel = function(options) {
        assertProperties(options, ['lang', 'langs', 'modules', 'read_only'], []);

        var self = {};
        self.lang = options.lang;
        self.langs = options.langs;
        self.modules = _.map(options.modules, moduleModel);
        self.readOnly = options.read_only;

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

        self.showComments = ko.observable(false);
        self.toggleComments = function() {
            self.showComments(!self.showComments());
        };

        self.showDefaultValues = ko.observable(false);
        self.toggleDefaultValues = function() {
            self.showDefaultValues(!self.showDefaultValues());
        };

        self.query = ko.observable('');
        self.clearQuery = function() {
            self.query('');
        };
        var match = function(needle, haystack) {
            return !needle || haystack.toLowerCase().indexOf(needle.toLowerCase()) !== -1;
        };
        self.query.subscribe(_.debounce(function(newValue) {
            _.each(self.modules, function(module) {
                var moduleIsVisible = match(newValue, self.translate(module.name));
                _.each(module.forms, function(form) {
                    var formIsVisible = match(newValue, self.translate(form.name));
                    _.each(form.questions, function(question) {
                        var questionIsVisible = match(newValue, question.value + self.translateQuestion(question));
                        questionIsVisible = questionIsVisible || _.find(question.options, function(option) {
                            return match(newValue, option.value + self.translateQuestion(option));
                        });
                        question.isVisible(questionIsVisible);
                        formIsVisible = formIsVisible || questionIsVisible;
                    });
                    form.hasVisibleDescendants(formIsVisible);
                    moduleIsVisible = moduleIsVisible || formIsVisible;
                });
                module.hasVisibleDescendants(moduleIsVisible);
            });
        }, 200));

        self.showLabels = ko.observable(true);
        self.showIds = ko.computed(function() {
            return !self.showLabels();
        });
        self.turnLabelsOn = function() {
            self.showLabels(true);
        };
        self.turnIdsOn = function() {
            self.showLabels(false);
        };

        self.translate = function(translations) {
            return utils.translateName(translations, self.lang, self.langs);
        };
        self.translateQuestion = function(question) {
            if (question.translations) {
                return utils.translateName(question.translations, self.lang, self.langs);
            }
            return question.label;  // hidden values don't have translations
        };

        return self;
    };

    var moduleModel = function(module) {
        var self = _.extend({}, module);

        self.url = hqImport("hqwebapp/js/initial_page_data").reverse("view_module", self.id);
        self.icon = utils.moduleIcon(self) + ' hq-icon';
        self.forms = _.map(self.forms, formModel);

        self.isSelected = ko.observable(true);

        self.hasVisibleDescendants = ko.observable(true);
        self.isVisible = ko.computed(function() {
            return self.isSelected() && self.hasVisibleDescendants();
        });

        return self;
    };

    var formModel = function(form) {
        var self = _.extend({}, form);

        self.url = hqImport("hqwebapp/js/initial_page_data").reverse("form_source", self.id);
        self.icon = utils.formIcon(self) + ' hq-icon';
        self.questions = _.map(self.questions, function(question) {
            return utils.questionModel(question);
        });

        self.isSelected = ko.observable(true);

        self.hasVisibleDescendants = ko.observable(true);
        self.isVisible = ko.computed(function() {
            return self.isSelected() && self.hasVisibleDescendants();
        });

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
            read_only: initialPageData.get("read_only"),
        });

        hqImport("hqwebapp/js/layout").setIsAppbuilderResizing(true);
        $("#hq-sidebar > nav").koApplyBindings(formSummaryMenu);
        $("#js-appmanager-body").koApplyBindings(formSummaryContent);

        formSummaryMenu.selectedItemId.subscribe(function(newValue) {
            formSummaryContent.selectedItemId(newValue);
        });
    });
});
