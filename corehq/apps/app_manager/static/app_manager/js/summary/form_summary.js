hqDefine('app_manager/js/summary/form_summary',[
    'jquery',
    'underscore',
    'knockout',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/assert_properties',
    'app_manager/js/summary/models',
    'app_manager/js/summary/utils',
    'app_manager/js/menu',  // enable lang switcher and "Updates to publish" banner
    'hqwebapp/js/knockout_bindings.ko', // popover
    'hqwebapp/js/components.ko',    // search box
], function ($, _, ko, initialPageData, assertProperties, models, utils) {

    var formSummaryControlModel = function (viewModels) {
        var self = {};
        _.extend(self, models.controlModel({
            onQuery: function (query) {
                var match = function (needle, haystack) {
                    return !needle || haystack.toLowerCase().indexOf(needle.trim().toLowerCase()) !== -1;
                };
                _.each(viewModels, function (viewModel) {
                    _.each(viewModel.modules, function (module) {
                        var moduleIsVisible = match(query, viewModel.translate(module.name));
                        _.each(module.forms, function (form) {
                            var formIsVisible = match(query, viewModel.translate(form.name));
                            _.each(form.questions, function (question) {
                                var questionIsVisible = match(query, question.value + viewModel.translateQuestion(question));
                                questionIsVisible = questionIsVisible || _.find(question.options, function (option) {
                                    return match(query, option.value + viewModel.translateQuestion(option));
                                });
                                var casePropsVisible = _.find(question.load_properties.concat(question.save_properties), function (prop) {
                                    return match(query, prop[0]) || match(query, prop[1]);
                                });
                                if (!viewModel.showCaseProperties() && casePropsVisible) {
                                    viewModel.showCaseProperties(true);
                                }
                                questionIsVisible = questionIsVisible || casePropsVisible;
                                question.matchesQuery(questionIsVisible);
                                formIsVisible = formIsVisible || questionIsVisible;
                            });
                            form.matchesQuery(formIsVisible);
                            moduleIsVisible = moduleIsVisible || formIsVisible;
                        });
                        module.matchesQuery(moduleIsVisible);
                    });
                })
                ;
            },
            query_label: gettext("Filter questions or cases"),
            onSelectMenuItem: function (selectedId) {
                _.each(viewModels, function (viewModel) {
                    _.each(viewModel.modules, function (module) {
                        module.isSelected(!selectedId || selectedId === module.id || _.find(module.forms, function (f) { return selectedId === f.id; }));
                        _.each(module.forms, function (form) {
                            form.isSelected(!selectedId || selectedId === form.id || selectedId === module.id);
                        });
                    });
                });
            },
        }));

        self.showCalculations = ko.observable(false);
        self.toggleCalculations = function () {
            self.showCalculations(!self.showCalculations());
        };

        self.showRelevance = ko.observable(false);
        self.toggleRelevance = function () {
            self.showRelevance(!self.showRelevance());
        };

        self.showConstraints = ko.observable(false);
        self.toggleConstraints = function () {
            self.showConstraints(!self.showConstraints());
        };

        self.showComments = ko.observable(false);
        self.toggleComments = function () {
            self.showComments(!self.showComments());
        };

        self.showDefaultValues = ko.observable(false);
        self.toggleDefaultValues = function () {
            self.showDefaultValues(!self.showDefaultValues());
        };

        self.showCaseProperties = ko.observable(false);
        self.toggleCaseProperties = function () {
            self.showCaseProperties(!self.showCaseProperties());
        };

        return self;
    };

    var formSummaryModel = function (options) {
        var self = models.contentModel(options);

        assertProperties.assertRequired(options, ['errors', 'modules']);
        self.errors = options.errors;
        self.modules = _.map(options.modules, models.moduleModel);
        return self;
    };

    $(function () {
        var lang = initialPageData.get('lang'),
            langs = initialPageData.get('langs');

        var formSummaryMenu = models.menuModel({
            items: _.map(initialPageData.get("modules"), function (module) {
                return models.menuItemModel({
                    id: module.id,
                    name: utils.translateName(module.name, lang, langs),
                    icon: utils.moduleIcon(module),
                    has_errors: false,
                    subitems: _.map(module.forms, function (form) {
                        return models.menuItemModel({
                            id: form.id,
                            name: utils.translateName(form.name, lang, langs),
                            icon: utils.formIcon(form),
                        });
                    }),
                });
            }),
            viewAllItems: gettext("View All Forms"),
        });

        var formSummaryContent = formSummaryModel({
            errors: initialPageData.get("errors"),
            form_name_map: initialPageData.get("form_name_map"),
            lang: lang,
            langs: langs,
            modules: initialPageData.get("modules"),
            read_only: initialPageData.get("read_only"),
        });

        var formSummaryController = formSummaryControlModel([formSummaryContent]);
        $("#form-summary-header").koApplyBindings(formSummaryController);
        models.initMenu([formSummaryContent], formSummaryMenu);
        models.initSummary(formSummaryContent, formSummaryController, "#form-summary");
    });
});
