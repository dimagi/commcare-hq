/**
 * Base models for app summary. Inherited by case summary and form summary.
 * Sets up a menu of items, to be linked with a set of content.
 */
hqDefine('app_manager/js/summary/models',[
    'jquery',
    'knockout',
    'underscore',
    'app_manager/js/summary/utils',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/assert_properties',
    'hqwebapp/js/layout',
], function ($, ko, _, utils, initialPageData, assertProperties, hqLayout) {

    var menuItemModel = function (options) {
        assertProperties.assert(options, ['id', 'name', 'icon'], ['subitems', 'has_errors']);
        var self = _.extend({
            has_errors: false,
        }, options);

        self.isSelected = ko.observable(false);
        self.select = function () {
            self.isSelected(true);
        };

        return self;
    };

    var menuModel = function (options) {
        assertProperties.assert(options, ['items', 'viewAllItems'], []);

        var self = {};

        self.items = options.items;
        self.viewAllItems = options.viewAllItems;

        self.selectedItemId = ko.observable('');      // blank indicates "View All"
        self.viewAllSelected = ko.computed(function () {
            return !self.selectedItemId();
        });

        self.select = function (item) {
            self.selectedItemId(item.id);
            _.each(self.items, function (i) {
                i.isSelected(item.id === i.id);
                _.each(i.subitems, function (s) {
                    s.isSelected(item.id === s.id);
                });
            });
        };
        self.selectAll = function () {
            self.select('');
        };

        return self;
    };

    var contentItemModel = function (options) {
        var self = _.extend({}, options);

        self.isSelected = ko.observable(true);  // based on what's selected in menu
        self.matchesQuery = ko.observable(true);   // based on what's entered in search box
        self.isVisible = ko.computed(function () {
            return self.isSelected() && self.matchesQuery();
        });

        return self;
    };

    var controlModel = function (options) {
        assertProperties.assertRequired(options, ['onQuery', 'onSelectMenuItem']);
        var self = {};

        // Connection to menu
        self.selectedItemId = ko.observable('');      // blank indicates "View All"
        self.selectedItemId.subscribe(function (selectedId) {
            options.onSelectMenuItem(selectedId);
        });

        // Search box behavior
        self.query = ko.observable('');
        self.queryLabel = options.query_label;
        self.onQuery = function () {
            options.onQuery(self.query());
        };

        // Handling of id/label switcher
        self.showLabels = ko.observable(true);
        self.showIds = ko.computed(function () {
            return !self.showLabels();
        });
        self.turnLabelsOn = function () {
            self.showLabels(true);
        };
        self.turnIdsOn = function () {
            self.showLabels(false);
        };

        return self;
    };

    var contentModel = function (options) {
        assertProperties.assertRequired(options, ['form_name_map', 'lang', 'langs', 'read_only']);
        var self = {};

        // Utilities
        self.lang = options.lang;
        self.langs = options.langs;
        self.questionIcon = utils.questionIcon;
        self.translate = function (translations) {
            return utils.translateName(translations, self.lang, self.langs);
        };
        self.translateQuestion = function (question) {
            if (question.translations) {
                return utils.translateName(question.translations, self.lang, self.langs);
            }
            return question.label;  // hidden values don't have translations
        };

        // Create "module -> form" link/text markup
        self.formNameMap = options.form_name_map;
        self.readOnly = options.read_only;
        self.moduleFormReference = function (formId) {
            var formData = self.formNameMap[formId];
            var template = self.readOnly
                ? "<%= moduleName %> &rarr; <%= formName %>"
                : "<a href='<%= moduleUrl %>'><%= moduleName %></a> &rarr; <a href='<%= formUrl %>'><%= formName %></a>"
            ;
            return _.template(template)({
                moduleName: self.translate(formData.module_name),
                moduleUrl: formData.module_url,
                formName: self.translate(formData.form_name),
                formUrl: formData.form_url,
            });
        };
        self.moduleReference = function (moduleId) {
            var moduleData = self.formNameMap[moduleId];
            var template = self.readOnly
                ? "<%= moduleName %>"
                : "<a href='<%= moduleUrl %>'><%= moduleName %></a>"
            ;
            return _.template(template)({
                moduleName: self.translate(moduleData.module_name),
                moduleUrl: moduleData.module_url,
            });
        };

        self.initController = function (controller) {
            _.extend(self, controller);
        };

        return self;
    };

    var moduleModel = function (module) {
        var self = contentItemModel(module);

        self.url = initialPageData.reverse("view_module", self.id);
        self.icon = utils.moduleIcon(self) + ' hq-icon';
        self.forms = _.map(self.forms, formModel);

        return self;
    };

    var formModel = function (form) {
        var self = contentItemModel(form);

        self.url = initialPageData.reverse("form_source", self.id);
        self.icon = utils.formIcon(self) + ' hq-icon';
        self.questions = _.map(self.questions, function (question) {
            return contentItemModel(_.defaults(question, {
                options: [],
            }));
        });

        return self;
    };

    var initMenu = function (contentInstances, menuInstance) {
        menuInstance.selectedItemId.subscribe(function (newValue) {
            _.each(contentInstances, function (contentInstance) {
                contentInstance.selectedItemId(newValue);
            });
        });
        $("#hq-sidebar > nav").koApplyBindings(menuInstance);
    };

    var initSummary = function (contentInstance, controller, contentDiv) {
        hqLayout.setIsAppbuilderResizing(true);
        contentInstance.initController(controller);
        $(contentDiv).koApplyBindings(contentInstance);
    };

    return {
        contentModel: contentModel,
        contentItemModel: contentItemModel,
        menuItemModel: menuItemModel,
        menuModel: menuModel,
        moduleModel: moduleModel,
        initMenu: initMenu,
        initSummary: initSummary,
        controlModel: controlModel,
    };
});
