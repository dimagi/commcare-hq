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
    'app_manager/js/widgets',       // version dropdown
    'analytix/js/kissmetrix',
    'DOMPurify/dist/purify.min',
], function ($, ko, _, utils, initialPageData, assertProperties, hqLayout, widgets, kissmetricsAnalytics, DOMPurify) {
    var menuItemModel = function (options) {
        assertProperties.assert(options, ['unique_id', 'name', 'icon'], ['subitems', 'has_errors', 'has_changes']);
        var self = _.extend({
            has_errors: false,
            has_changes: false,
        }, options);

        self.isSelected = ko.observable(false);
        self.select = function () {
            self.isSelected(true);
        };

        return self;
    };

    var menuModel = function (options) {
        assertProperties.assert(options, ['items', 'viewAllItems'], ['viewChanged']);

        var self = {};

        self.items = options.items;
        self.viewAllItems = options.viewAllItems;

        self.selectedItemId = ko.observable('');      // blank indicates "View All"
        self.selectedItemId.extend({ notify: 'always' });

        self.select = function (item) {
            self.selectedItemId(item.unique_id);
            self.viewChangedOnlySelected(false);
            _.each(self.items, function (i) {
                i.isSelected(item.unique_id === i.unique_id);
                _.each(i.subitems, function (s) {
                    s.isSelected(item.unique_id === s.unique_id);
                });
            });
        };
        self.selectAll = function () {
            self.select('');
        };

        self.viewChanged = options.viewChanged;
        self.viewChangedOnlySelected = ko.observable(false);
        self.viewChangedOnly = function () {
            self.viewChangedOnlySelected(true);
            _.each(self.items, function (i) {
                i.isSelected(i.has_changes);
                _.each(i.subitems, function (s) {
                    s.isSelected(s.has_changes);
                });
            });
        };

        self.viewAllSelected = ko.computed(function () {
            return !self.selectedItemId() && !self.viewChangedOnlySelected();
        });


        return self;
    };

    var contentItemModel = function (options) {
        var self = _.extend({}, options);

        var basePopoverOptions = {
            "trigger": "hover",
            "placement": "auto right",
            "container": "body",
            "html": true,
        };

        self.children = _.map(options.children, function (child) { return contentItemModel(child); });
        self.isSelected = ko.observable(true);  // based on what's selected in menu
        self.matchesQuery = ko.observable(true);   // based on what's entered in search box
        self.isVisible = ko.computed(function () {
            return self.isSelected() && self.matchesQuery();
        });
        self.getDiffPopover = function (change, attribute) {
            if (!change || !change['type']){
                return {};
            }
            var oldValue = change['old_value'],
                newValue = change['new_value'],
                content = '',
                attributeToName = {
                    'module': gettext("Module"),
                    'form': gettext("Form"),
                    'question': gettext("Question"),
                    'name': gettext("Name"),
                    'label': gettext("Label"),
                    'type': gettext("Question Type"),
                    'value': gettext("Question Value"),
                    'options': gettext("Option"),
                    'calculate': gettext("Calculate condition"),
                    'relevant': gettext("Display condition"),
                    'required': gettext("Required"),
                    'comment': gettext("Question Comment"),
                    'setvalue': gettext("Default Value"),
                    'constraint': gettext("Validation Condition"),
                    'short_comment': gettext("Comment"),
                    'form_filter': gettext("Form Filter"),
                    'module_filter': gettext("Module Filter"),
                };
            if (oldValue || newValue) {
                content = "<dl>";
                content += _getPopoverText(gettext('Old Value'), oldValue);
                content += _getPopoverText(gettext('New Value'), newValue);
                content += "</dl>";
            }
            return _.defaults({
                "title": attributeToName[attribute] + " " + gettext(change["type"]),
                "content": content,
            }, basePopoverOptions);
        };
        self.getLoadSavePopover = function (attribute, caseType, caseProperty) {
            try {
                var change = self.changes[attribute][caseType][caseProperty];
            } catch (e) {
                return {};
            }
            if (!change) {
                return {};
            }
            var title = {
                    'load_properties': gettext("Loaded Case Properties"),
                    'save_properties': gettext("Saved Case Properties"),
                }[attribute],
                loadOrSave = {
                    'load_properties': gettext("load"),
                    'save_properties': gettext("save"),
                }[attribute],
                content = "<dl>" + _getPopoverText(
                    gettext("Case Property") + " " + loadOrSave + " " + gettext(change['type']),
                    gettext("Case Property") + " <strong>" + caseProperty + "</strong> "+ gettext("of Case Type") + " <strong>" + caseType + "</strong> " + gettext(change['type'])
                ) + "</dl>";

            return _.defaults({
                "title": title,
                "content": content,
            }, basePopoverOptions);
        };
        var _getPopoverText = function (title, value) {
            if (!value) {
                return '';
            }

            var text = "<dt>" + title + "</dt>";
            if (value instanceof Object) { // translatable property
                text += "<dl>";
                for (var translationKey in value) {
                    text += "<dt>" + translationKey + "</dt>";
                    text += "<dd>" + DOMPurify.sanitize(value[translationKey]) + "</dd>";
                }
                text += "</dl>";
            } else {
                text += "<dd>" + DOMPurify.sanitize(value) + "</dd>";
            }
            return text;
        };

        self.getDiffClass = function (attribute) {
            return self.changes[attribute]['type'] ? 'diff-' + self.changes[attribute]['type'] : '';
        };
        self.getOptionsDiffClass = function (option) {
            try {
                return 'diff-' + self.changes['options'][option]['type'];
            } catch (e) {
                return '';
            }
        };
        self.getLoadSaveDiffClass = function (attribute, caseType, caseProperty) {
            try {
                return 'diff-' + self.changes[attribute][caseType][caseProperty]['type'];
            } catch (e) {
                return '';
            }
        };

        return self;
    };

    var controlModel = function (options) {
        assertProperties.assertRequired(options, ['onQuery', 'onSelectMenuItem', 'visibleAppIds', 'versionUrlName']);
        var self = {};

        // Connection to menu
        self.selectedItemId = ko.observable('');      // blank indicates "View All"
        self.selectedItemId.extend({ notify: 'always' });
        self.selectedItemId.subscribe(function (selectedId) {
            options.onSelectMenuItem(selectedId);
        });
        self.selectChangedOnly = function () {
            options.onSelectChangesOnlyMenuItem();
        };

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

        // App diff controls
        self.firstAppId = ko.observable();  // this gets prepopulated by select2
        self.secondAppId = ko.observable(); // this gets prepopulated by select2
        self.showChangeVersions = ko.computed(function () {
            return self.firstAppId() !== options.visibleAppIds[0] || self.secondAppId() !== options.visibleAppIds[1];
        });
        self.changeVersions = function () {
            if (self.firstAppId && self.secondAppId()) {
                kissmetricsAnalytics.track.event("Compare App Versions: Change Version Using Dropdown");
                window.location.href =  initialPageData.reverse(options.versionUrlName, self.firstAppId(), self.secondAppId());
            } else {
                window.location.href = initialPageData.reverse(options.versionUrlName, self.firstAppId());
            }
        };

        return self;
    };

    var contentModel = function (options) {
        assertProperties.assertRequired(options, ['form_name_map', 'lang', 'langs', 'read_only', 'appId']);
        var self = {};

        // Utilities
        self.lang = options.lang;
        self.langs = options.langs;
        self.questionIcon = utils.questionIcon;
        self.appId = options.appId;
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

        self.url = initialPageData.reverse("view_module", self.unique_id);
        self.icon = utils.moduleIcon(self) + ' hq-icon';
        self.forms = _.map(self.forms, formModel);

        return self;
    };

    var formModel = function (form) {
        var self = contentItemModel(form);

        self.url = initialPageData.reverse("form_source", self.unique_id);
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
        menuInstance.viewChangedOnlySelected.subscribe(function (newValue) {
            if (newValue) {
                _.each(contentInstances, function (contentInstance) {
                    contentInstance.selectChangedOnly();
                });
            }
        });
        $("#hq-sidebar > nav").koApplyBindings(menuInstance);
    };

    var initSummary = function (contentInstance, controller, contentDiv) {
        hqLayout.setIsAppbuilderResizing(true);
        contentInstance.initController(controller);
        $(contentDiv).koApplyBindings(contentInstance);
    };

    var initVersionsBox = function ($dropdown, initialValue) {
        widgets.initVersionDropdown($dropdown, {
            initialValue: initialValue,
            width: "150px",
            extraValues: [{id: initialPageData.get("latest_app_id"), text: gettext("Latest saved")}],
        });
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
        initVersionsBox: initVersionsBox,
    };
});
