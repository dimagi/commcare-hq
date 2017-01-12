/*globals $, _, uiElement, eventize, COMMCAREHQ, DOMPurify */

hqDefine('app_manager/js/detail-screen-config.js', function () {
    var module = {};

    module.CC_DETAIL_SCREEN = {
        getFieldHtml: function (field) {
            var text = field;
            if (module.CC_DETAIL_SCREEN.isAttachmentProperty(text)) {
                text = text.substring(text.indexOf(":") + 1);
            }
            var parts = text.split('/');
            // wrap all parts but the last in a label style
            for (var j = 0; j < parts.length - 1; j++) {
                parts[j] = ('<span class="label label-info">'
                            + parts[j] + '</span>');
            }
            if (parts[j][0] == '#') {
                parts[j] = ('<span class="label label-info">'
                            + module.CC_DETAIL_SCREEN.toTitleCase(parts[j]) + '</span>');
            } else {
                parts[j] = ('<code style="display: inline-block;">'
                            + parts[j] + '</code>');
            }
            return parts.join('<span style="color: #DDD;">/</span>');
        },
        isAttachmentProperty: function (value) {
            return value && value.indexOf("attachment:") === 0;
        },
        toTitleCase: function (str) {
            return (str
                .replace(/[_\/-]/g, ' ')
                .replace(/#/g, '')
            ).replace(/\w\S*/g, function (txt) {
                return txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase();
            });
        },
        /**
         * Enable autocomplete on the given jquery element with the given autocomplete
         * options.
         * @param $elem
         * @param options: Array of strings.
         */
        setUpAutocomplete: function($elem, options){
            if (!_.contains(options, $elem.value)) {
                options.unshift($elem.value);
            }
            $elem.$edit_view.select2({
                minimumInputLength: 0,
                delay: 0,
                data: {
                    results: _.map(options, function(o) {
                        return {
                            id: o,
                            text: o,
                        };
                    }),
                },
                // Allow manually entered text in drop down, which is not supported by legacy select2.
                createSearchChoice: function(term, data) {
                    if (!_.find(data, function(d) { return d.text === term; })) {
                        return {
                            id: term,
                            text: term,
                        };
                    }
                },
                escapeMarkup: function (m) { return DOMPurify.sanitize(m); },
                formatResult: function(result) {
                    var formatted = result.id;
                    if (module.CC_DETAIL_SCREEN.isAttachmentProperty(result.id)) {
                        formatted = (
                            '<i class="fa fa-paperclip"></i> ' +
                            result.id.substring(result.id.indexOf(":") + 1)
                        );
                    }
                    return DOMPurify.sanitize(formatted);
                },
            }).on('change', function() {
                $elem.val($elem.$edit_view.value);
                $elem.fire('change');
            });
            return $elem;
        }

    };

    // saveButton is a required parameter
    var SortRow = function(params){
        var self = this;
        params = params || {};

        self.textField = uiElement.input().val(typeof params.field !== 'undefined' ? params.field : "");
        module.CC_DETAIL_SCREEN.setUpAutocomplete(this.textField, params.properties);

        self.showWarning = ko.observable(false);
        self.hasValidPropertyName = function(){
            return module.DetailScreenConfig.field_val_re.test(self.textField.val());
        };
        self.display = ko.observable(typeof params.display !== 'undefined' ? params.display : "");
        self.display.subscribe(function () {
            self.notifyButton();
        });
        self.toTitleCase = module.CC_DETAIL_SCREEN.toTitleCase;
        this.textField.on('change', function(){
            if (!self.hasValidPropertyName()){
                self.showWarning(true);
            } else {
                self.showWarning(false);
                self.display(self.toTitleCase(this.val()));
                self.notifyButton();
            }
        });

        self.type = ko.observable(typeof params.type !== 'undefined' ? params.type : "");
        self.type.subscribe(function () {
            self.notifyButton();
        });
        self.direction = ko.observable(typeof params.direction !== 'undefined' ? params.direction : "");
        self.direction.subscribe(function () {
            self.notifyButton();
        });

        self.notifyButton = function(){
            params.saveButton.fire('change');
        };

        self.ascendText = ko.computed(function () {
            var type = self.type();
            // This is here for the CACHE_AND_INDEX feature
            if (type === 'plain' || type === 'index') {
                return 'Increasing (a, b, c)';
            } else if (type === 'date') {
                return 'Increasing (May 1st, May 2nd)';
            } else if (type === 'int') {
                return 'Increasing (1, 2, 3)';
            } else if (type === 'double' || type === 'distance') {
                return 'Increasing (1.1, 1.2, 1.3)';
            }
        });

        self.descendText = ko.computed(function () {
            var type = self.type();
            if (type === 'plain' || type === 'index') {
                return 'Decreasing (c, b, a)';
            } else if (type === 'date') {
                return 'Decreasing (May 2nd, May 1st)'
            } else if (type === 'int') {
                return 'Decreasing (3, 2, 1)';
            } else if (type === 'double' || type === 'distance') {
                return 'Decreasing (1.3, 1.2, 1.1)';
            }
        });
    };

    /**
     *
     * @param properties
     * @param saveButton
     * The button that should be activated when something changes
     * @constructor
     */
    var SortRows = function (properties, saveButton) {
        var self = this;
        self.sortRows = ko.observableArray([]);

        self.addSortRow = function (field, type, direction, display, notify) {
            self.sortRows.push(new SortRow({
                field: field,
                type: type,
                direction: direction,
                display: display,
                saveButton: saveButton,
                properties: properties
            }));
            if (notify) {
                saveButton.fire('change');
            }
        };
        self.removeSortRow = function (row) {
            self.sortRows.remove(row);
            saveButton.fire('change');
        };

        self.rowCount = ko.computed(function () {
            return self.sortRows().length;
        });

        self.showing = ko.computed(function(){
            return self.rowCount() > 0;
        });
    };

    var filterViewModel = function(filterText, saveButton) {
        var self = this;
        self.filterText = ko.observable(typeof filterText == "string" && filterText.length > 0 ? filterText : "");
        self.showing = ko.observable(self.filterText() !== "");

        self.filterText.subscribe(function(){
            saveButton.fire('change');
        });
        self.showing.subscribe(function(){
            saveButton.fire('change');
        });

        self.serialize = function(){
            if (self.showing()) {
                return self.filterText();
            }
            return null;
        };
    };

    var searchViewModel = function (searchProperties, includeClosed, defaultProperties, lang, saveButton) {
        var self = this,
            DEFAULT_CLAIM_RELEVANT= "count(instance('casedb')/casedb/case[@case_id=instance('commcaresession')/session/data/case_id]) = 0";

        var SearchProperty = function (name, label) {
            var self = this;
            self.name = ko.observable(name);
            self.label = ko.observable(label);

            self.name.subscribe(function () {
                saveButton.fire('change');
            });
            self.label.subscribe(function () {
                saveButton.fire('change');
            });
        };

        var DefaultProperty = function (property, defaultValue) {
            var self = this;
            self.property = ko.observable(property);
            self.defaultValue = ko.observable(defaultValue);

            self.property.subscribe(function () {
                saveButton.fire('change');
            });
            self.defaultValue.subscribe(function () {
                saveButton.fire('change');
            });
        };

        self.relevant = ko.observable();
        self.default_relevant = ko.observable(true);
        self.includeClosed = ko.observable(includeClosed);
        self.searchProperties = ko.observableArray();
        self.defaultProperties = ko.observableArray();

        if (searchProperties.length > 0) {
            for (var i = 0; i < searchProperties.length; i++) {
                // property labels come in keyed by lang.
                var label = searchProperties[i].label[lang];
                self.searchProperties.push(new SearchProperty(
                    searchProperties[i].name,
                    label
                ));
            }
        } else {
            self.searchProperties.push(new SearchProperty('', ''));
        }

        self.addProperty = function () {
            self.searchProperties.push(new SearchProperty('', ''));
        };
        self.removeProperty = function (property) {
            self.searchProperties.remove(property);
        };
        self._getProperties = function () {
            // i.e. [{'name': p.name, 'label': p.label} for p in self.searchProperties if p.name]
            return _.map(
                _.filter(
                    self.searchProperties(),
                    function (p) { return p.name().length > 0; }  // Skip properties where name is blank
                ),
                function (p) {
                    return {
                        name: p.name(),
                        label: p.label().length ? p.label() : p.name(),  // If label isn't set, use name
                    };
                }
            );
        };

        if (defaultProperties.length > 0) {
            for (var k = 0; k < defaultProperties.length; k++) {
                self.defaultProperties.push(new DefaultProperty(
                    defaultProperties[k].property,
                    defaultProperties[k].defaultValue
                ));
            }
        } else {
            self.defaultProperties.push(new DefaultProperty('', ''));
        }
        self.addDefaultProperty = function () {
            self.defaultProperties.push(new DefaultProperty('',''));
        };
        self.removeDefaultProperty = function (property) {
            self.defaultProperties.remove(property);
        };
        self._getDefaultProperties = function () {
            return _.map(
                _.filter(
                    self.defaultProperties(),
                    function (p) { return p.property().length > 0; }  // Skip properties where property is blank
                ),
                function (p) {
                    return {
                        property: p.property(),
                        defaultValue: p.defaultValue(),
                    };
                }
            );
        };
        self._getRelevant = function() {
            if (self.default_relevant()) {
                if (!self.relevant() || self.relevant().trim() === "") {
                    return DEFAULT_CLAIM_RELEVANT;
                } else {
                    return "(" + DEFAULT_CLAIM_RELEVANT + ") and (" + self.relevant().trim() + ")";
                }
            }
            return self.relevant().trim();
        };

        self.serialize = function () {
            return {
                properties: self._getProperties(),
                relevant: self._getRelevant(),
                include_closed: self.includeClosed(),
                default_properties: self._getDefaultProperties(),
            };
        };

        self.includeClosed.subscribe(function () {
            saveButton.fire('change');
        });
        self.default_relevant.subscribe(function () {
            saveButton.fire('change');
        });
        self.searchProperties.subscribe(function () {
            saveButton.fire('change');
        });
        self.defaultProperties.subscribe(function () {
            saveButton.fire('change');
        });
    };

    var caseListLookupViewModel = function($el, state, lang, saveButton) {
        'use strict';
        var self = this,
            detail_type = $el.data('detail-type');

        var ObservableKeyValue = function(obs){
            this.key = ko.observable(obs.key);
            this.value = ko.observable(obs.value);
        };

        var _fireChange = function(){
            saveButton.fire('change');
        };

        self.initSaveButtonListeners = function($el){
            $el.find('input[type=text], textarea').on('textchange', _fireChange);
            $el.find('input[type=checkbox]').on('change', _fireChange);
            $el.find(".case-list-lookup-icon button").on("click", _fireChange); // Trigger save button when icon upload buttons are clicked
        };

        var _remove_empty = function(type){
            self[type].remove(function(t){
                var is_blank = (!t.key() && !t.value());
                return is_blank;
            });
        };

        self.add_item = function(type){
            _remove_empty(type);
            var data = (type === 'extras') ? {key: '', value: ''} : {key: ''};
            self[type].push(new ObservableKeyValue(data));
        };

        self.remove_item = function(type, item){
            self[type].remove(item);
            if (self[type]().length === 0){
                self.add_item(type);
            }
            _fireChange();
        };

        var _trimmed_extras = function(){
            return _.compact(_.map(self.extras(), function(extra){
                if (!(extra.key() === "" && extra.value() ==="")){
                    return {key: extra.key(), value: extra.value()};
                }
            }));
        };

        var _trimmed_responses = function(){
            return _.compact(_.map(self.responses(), function(response){
                if (response.key() !== ""){
                    return {key: response.key()};
                }
            }));
        };

        self.serialize = function(){
            var image_path = $el.find(".case-list-lookup-icon input[type=hidden]").val() || null;

            var data = {
                lookup_enabled: self.lookup_enabled(),
                lookup_autolaunch: self.lookup_autolaunch(),
                lookup_action: self.lookup_action(),
                lookup_name: self.lookup_name(),
                lookup_extras: _trimmed_extras(),
                lookup_responses: _trimmed_responses(),
                lookup_image: image_path,
                lookup_display_results: self.lookup_display_results(),
                lookup_field_header: self.lookup_field_header.val(),
                lookup_field_template: self.lookup_field_template(),
            };

            return data;
        };

        var _validate_inputs = function(errors){
            errors = errors || [];
            $el.find('input[required]').each(function(){
                var $this = $(this);
                if ($this.val().trim().length === 0){
                    $this.closest('.form-group').addClass('has-error');
                    var $help = $this.siblings('.help-block');
                    $help.show();
                    errors.push($help.text());
                }
                else {
                    $this.closest('.form-group').removeClass('has-error');
                    $this.siblings('.help-block').hide();
                }
            });
            return errors;
        };

        var _validate_extras = function(errors){
            errors = errors || [];
            var $extra = $el.find("#" + detail_type + "-extras"),
                $extra_help = $extra.find(".help-block");

            if (!_trimmed_extras().length){
                $extra.addClass('has-error');
                $extra_help.show();
                errors.push($extra_help.text());
            }
            else {
                $extra.removeClass('has-error');
                $extra_help.hide();
            }
            return errors;
        };

        var _validate_responses = function(errors){
            errors = errors || [];
            var $response = $el.find("#" + detail_type + "-responses"),
                $response_help = $response.find(".help-block");

            if (!_trimmed_responses().length){
                $response.addClass('has-error');
                $response_help.show();
                errors.push($response_help.text());
            }
            else {
                $response.removeClass('has-error');
                $response_help.hide();
            }
            return errors;
        };

        self.validate = function(){
            var errors = [];

            $("#message-alerts > div").each(function(){
                $(this).alert('close');
            });

            if (self.lookup_enabled()){
                _validate_inputs(errors);
                _validate_extras(errors);
                _validate_responses(errors);
            }

            if (errors.length) {
                _.each(errors, function(error){
                    alert_user(error, "danger");
                });
                return false;
            }
            return true;
        };

        self.$el = $el;
        self.$form = $el.find('form');

        self.lookup_enabled = ko.observable(state.lookup_enabled);
        self.lookup_autolaunch = ko.observable(state.lookup_autolaunch);
        self.lookup_action = ko.observable(state.lookup_action);
        self.lookup_name = ko.observable(state.lookup_name);
        self.extras = ko.observableArray(ko.utils.arrayMap(state.lookup_extras, function(extra){
            return new ObservableKeyValue(extra);
        }));
        self.responses = ko.observableArray(ko.utils.arrayMap(state.lookup_responses, function(response){
            return new ObservableKeyValue(response);
        }));

        if (self.extras().length === 0){
            self.add_item('extras');
        }
        if (self.responses().length === 0){
            self.add_item('responses');
        }

        self.lookup_display_results = ko.observable(state.lookup_display_results);
        var invisible = "", visible = "";
        if (state.lookup_field_header[lang]) {
            visible = invisible = state.lookup_field_header[lang]
        } else {
            _.each(_.keys(state.lookup_field_header), function(lang) {
                if (state.lookup_field_header[lang]) {
                    visible = state.lookup_field_header[lang] + langcodeTag.LANG_DELIN + lang;
                }
            });
        }

        self.lookup_field_header = uiElement.input().val(
            invisible
        );
        self.lookup_field_header.setVisibleValue(visible);
        self.lookup_field_header.observableVal = ko.observable(self.lookup_field_header.val());
        self.lookup_field_header.on('change', function () {
            self.lookup_field_header.observableVal(self.lookup_field_header.val());
            _fireChange();  // input node created too late for initSaveButtonListeners
        });
        self.lookup_field_template = ko.observable(state.lookup_field_template || '@case_id');

        self.show_add_extra = ko.computed(function(){
            if (self.extras().length){
                var last_key = self.extras()[self.extras().length - 1].key(),
                    last_value = self.extras()[self.extras().length - 1].value();
                return !(last_key === "" && last_value === "");
            }
            return true;
        });

        self.show_add_response = ko.computed(function(){
            if (self.responses().length){
                var last_key = self.responses()[self.responses().length - 1].key();
                return last_key !== "";
            }
            return true;
        });

        self.initSaveButtonListeners(self.$el);
    };

    module.ParentSelect = function (init) {
        var self = this;
        var defaultModule = _(init.parentModules).findWhere({is_parent: true});
        self.moduleId = ko.observable(init.moduleId || (defaultModule ? defaultModule.unique_id : null));
        self.active = ko.observable(init.active);
        self.parentModules = ko.observable(init.parentModules);
        self.lang = ko.observable(init.lang);
        self.langs = ko.observable(init.langs);
        function getTranslation(name, langs) {
            var firstLang = _(langs).find(function (lang) {
                return name[lang];
            });
            return name[firstLang];
        }
        self.moduleOptions = ko.computed(function () {
            return _(self.parentModules()).map(function (module) {
                var STAR = '\u2605', SPACE = '\u3000';
                var marker = (module.is_parent ? STAR : SPACE);
                return {
                    value: module.unique_id,
                    label: marker + ' ' + getTranslation(module.name, [self.lang()].concat(self.langs()))
                };
            });
        });
    };

    var FixtureSelect = function (init) {
        var self = this;
        self.active = ko.observable(init.active);
        self.fixtureType = ko.observable(init.fixtureType);
        self.displayColumn = ko.observable(init.displayColumn);
        self.localize = ko.observable(init.localize);
        self.variableColumn = ko.observable(init.variableColumn);
        self.xpath = ko.observable(init.xpath);
        self.fixture_columns = ko.computed(function() {
            var columns_for_type = init.fixture_columns_by_type[self.fixtureType()],
                default_option = [gettext("Select One")];
            return default_option.concat(columns_for_type);
        });
    };

    module.DetailScreenConfig = (function () {
        "use strict";

        function getPropertyTitle(property) {
            // Strip "<prefix>:" before converting to title case.
            // This is aimed at prefixes like ledger: and attachment:
            var i = property.indexOf(":");
            return module.CC_DETAIL_SCREEN.toTitleCase(property.substring(i + 1));
        }

        var DetailScreenConfig, Screen, Column, sortRows;
        var word = '[a-zA-Z][\\w_-]*';

        Column = (function () {
            function Column(col, screen) {
                /*
                    column properites: model, field, header, format
                    column extras: enum, late_flag
                */
                var that = this;
                eventize(this);
                this.original = JSON.parse(JSON.stringify(col));

                // Set defaults for normal (non-tab) column attributes
                var defaults = {
                    calc_xpath: ".",
                    enum: [],
                    field: "",
                    filter_xpath: "",
                    format: "plain",
                    graph_configuration: {},
                    hasAutocomplete: false,
                    header: {},
                    model: screen.model,
                    time_ago_interval: DetailScreenConfig.TIME_AGO.year,
                };
                _.each(_.keys(defaults), function(key) {
                    that.original[key] = that.original[key] || defaults[key];
                });
                this.original.late_flag = _.isNumber(this.original.late_flag) ? this.original.late_flag : 30;

                this.original.case_tile_field = ko.utils.unwrapObservable(this.original.case_tile_field) || "";
                this.case_tile_field = ko.observable(this.original.case_tile_field);

                // Set up tab attributes
                var tabDefaults = {
                    isTab: false,
                    hasNodeset: false,
                    nodeset: "",
                };
                _.each(_.keys(tabDefaults), function(key) {
                    that.original[key] = that.original[key] || tabDefaults[key];
                });
                _.extend(this, _.pick(this.original, _.keys(tabDefaults)));

                this.screen = screen;
                this.lang = screen.lang;
                this.model = uiElement.select([
                    {label: "Case", value: "case"}
                ]).val(this.original.model);

                var icon = (module.CC_DETAIL_SCREEN.isAttachmentProperty(this.original.field)
                   ? COMMCAREHQ.icons.PAPERCLIP : null);
                this.field = uiElement.input(this.original.field).setIcon(icon);

                // Make it possible to observe changes to this.field
                // note that observableVal is read only!
                // Writing to it will not update the value of the this.field text input
                this.field.observableVal = ko.observable(this.field.val());
                this.field.on("change", function(){
                    that.field.observableVal(that.field.val());
                });

                (function () {
                    var i, lang, visibleVal = "", invisibleVal = "", nodesetVal;
                    if (that.original.header && that.original.header[that.lang]) {
                        visibleVal = invisibleVal = that.original.header[that.lang];
                    } else {
                        for (i = 0; i < that.screen.langs.length; i += 1) {
                            lang = that.screen.langs[i];
                            if (that.original.header[lang]) {
                                visibleVal = that.original.header[lang] + langcodeTag.LANG_DELIN + lang;
                                break;
                            }
                        }
                    }
                    that.header = uiElement.input().val(invisibleVal);
                    that.header.setVisibleValue(visibleVal);

                    that.nodeset = uiElement.input().val(that.original.nodeset);
                    if (that.isTab) {
                        // hack to wait until the input's there to prepend the Tab: label.
                        setTimeout(function () {
                            that.header.ui.addClass('input-group').prepend($('<span class="input-group-addon">Tab</span>'));
                            that.nodeset.ui.addClass('input-group').prepend($('<span class="input-group-addon">Nodeset</span>'));
                        }, 0);

                        // Observe nodeset values for the sake of validation
                        if (that.hasNodeset) {
                            that.nodeset.observableVal = ko.observable(that.original.nodeset);
                            that.nodeset.on("change", function(){
                                that.nodeset.observableVal(that.nodeset.val());
                            });
                        }
                    }
                }());

                this.saveAttempted = ko.observable(false);
                this.showWarning = ko.computed(function() {
                    if (this.isTab) {
                        // Data tab missing its nodeset
                        return this.hasNodeset && !this.nodeset.observableVal();
                    }
                    // Invalid property name
                    return (this.field.observableVal() || this.saveAttempted()) && !DetailScreenConfig.field_val_re.test(this.field.observableVal());
                }, this);

                // Add the graphing option if this is a graph so that we can set the value to graph
                var menuOptions = DetailScreenConfig.MENU_OPTIONS;
                if (this.original.format === "graph"){
                    menuOptions = menuOptions.concat([{value: "graph", label: ""}]);
                }

                this.format = uiElement.select(menuOptions).val(this.original.format || null);

                (function () {
                    var o = {
                        lang: that.lang,
                        langs: that.screen.langs,
                        module_id: that.screen.config.module_id,
                        items: that.original['enum'],
                        property_name: that.field,
                        multimedia: that.screen.config.multimedia,
                        values_are_icons: that.original.format == 'enum-image',
                    };
                    that.enum_extra = uiElement.key_value_mapping(o);
                }());
                var GraphConfigurationUiElement = hqImport('app_manager/js/graph-config.js').GraphConfigurationUiElement;
                this.graph_extra = new GraphConfigurationUiElement({
                    childCaseTypes: this.screen.childCaseTypes,
                    fixtures: this.screen.fixtures,
                    lang: this.lang,
                    langs: this.screen.langs,
                    name: this.header.val()
                }, this.original.graph_configuration);
                this.header.on("change", function(){
                    // The graph should always have the same name as the Column
                    that.graph_extra.setName(that.header.val());
                });

                this.late_flag_extra = uiElement.input().val(this.original.late_flag.toString());
                this.late_flag_extra.ui.find('input').css('width', 'auto').css("display", "inline-block");
                this.late_flag_extra.ui.prepend($('<span>' + DetailScreenConfig.message.LATE_FLAG_EXTRA_LABEL + '</span>'));

                this.filter_xpath_extra = uiElement.input().val(this.original.filter_xpath.toString());
                this.filter_xpath_extra.ui.prepend($('<div/>').text(DetailScreenConfig.message.FILTER_XPATH_EXTRA_LABEL));

                this.calc_xpath_extra = uiElement.input().val(this.original.calc_xpath.toString());
                this.calc_xpath_extra.ui.prepend($('<div/>').text(DetailScreenConfig.message.CALC_XPATH_EXTRA_LABEL));

                this.time_ago_extra = uiElement.select([
                    {label: DetailScreenConfig.message.TIME_AGO_INTERVAL.YEARS, value: DetailScreenConfig.TIME_AGO.year},
                    {label: DetailScreenConfig.message.TIME_AGO_INTERVAL.MONTHS, value: DetailScreenConfig.TIME_AGO.month},
                    {label: DetailScreenConfig.message.TIME_AGO_INTERVAL.WEEKS, value: DetailScreenConfig.TIME_AGO.week},
                    {label: DetailScreenConfig.message.TIME_AGO_INTERVAL.DAYS, value: DetailScreenConfig.TIME_AGO.day},
                    {label: DetailScreenConfig.message.TIME_AGO_INTERVAL.DAYS_UNTIL, value: -DetailScreenConfig.TIME_AGO.day},
                    {label: DetailScreenConfig.message.TIME_AGO_INTERVAL.WEEKS_UNTIL, value: -DetailScreenConfig.TIME_AGO.week},
                    {label: DetailScreenConfig.message.TIME_AGO_INTERVAL.MONTHS_UNTIL, value: -DetailScreenConfig.TIME_AGO.month}
                ]).val(this.original.time_ago_interval.toString());
                this.time_ago_extra.ui.prepend($('<div/>').text(DetailScreenConfig.message.TIME_AGO_EXTRA_LABEL));

                function fireChange() {
                    that.fire('change');
                }
                _.each([
                    'model',
                    'field',
                    'header',
                    'nodeset',
                    'format',
                    'enum_extra',
                    'graph_extra',
                    'late_flag_extra',
                    'filter_xpath_extra',
                    'calc_xpath_extra',
                    'time_ago_extra'
                ], function(element) {
                    that[element].on('change', fireChange);
                });
                this.case_tile_field.subscribe(fireChange);

                this.$format = $('<div/>').append(this.format.ui);
                this.$format.find("select").css("margin-bottom", "5px");
                this.format.on('change', function () {
                    // Prevent this from running on page load before init
                    if (that.format.ui.parent().length > 0) {
                        that.enum_extra.ui.detach();
                        that.graph_extra.ui.detach();
                        that.late_flag_extra.ui.detach();
                        that.filter_xpath_extra.ui.detach();
                        that.calc_xpath_extra.ui.detach();
                        that.time_ago_extra.ui.detach();

                        if (this.val() === "enum" || this.val() === "enum-image") {
                            that.enum_extra.values_are_icons(this.val() === 'enum-image');
                            that.format.ui.parent().append(that.enum_extra.ui);
                        } else if (this.val() === "graph") {
                            // Replace format select with edit button
                            var parent = that.format.ui.parent();
                            parent.empty();
                            parent.append(that.graph_extra.ui);
                        } else if (this.val() === 'late-flag') {
                            that.format.ui.parent().append(that.late_flag_extra.ui);
                            var input = that.late_flag_extra.ui.find('input');
                            input.change(function() {
                                that.late_flag_extra.value = input.val();
                                fireChange();
                            });
                        } else if (this.val() === 'filter') {
                            that.format.ui.parent().append(that.filter_xpath_extra.ui);
                            var input = that.filter_xpath_extra.ui.find('input');
                            input.change(function() {
                                that.filter_xpath_extra.value = input.val();
                                fireChange();
                            });
                        } else if (this.val() === 'calculate') {
                            that.format.ui.parent().append(that.calc_xpath_extra.ui);
                            var input = that.calc_xpath_extra.ui.find('input');
                            input.change(function() {
                                that.calc_xpath_extra.value = input.val();
                                fireChange();
                            });
                        } else if (this.val() === 'time-ago') {
                            that.format.ui.parent().append(that.time_ago_extra.ui);
                            var select = that.time_ago_extra.ui.find('select');
                            select.change(function() {
                                that.time_ago_extra.value = select.val();
                                fireChange();
                            });
                        }
                    }
                }).fire('change');
                // Note that bind to the $edit_view for this google analytics event
                // (as opposed to the format object itself)
                // because this way the events are not fired during the initialization
                // of the page.
                this.format.$edit_view.on("change", function(event){
                    ga_track_event('Case List Config', 'Display Format', event.target.value);
                });
            }

            Column.init = function (col, screen) {
                return new Column(col, screen);
            };
            Column.prototype = {
                serialize: function () {
                    var column = this.original;
                    column.field = this.field.val();
                    column.header[this.lang] = this.header.val();
                    column.nodeset = this.nodeset.val();
                    column.format = this.format.val();
                    column.enum = this.enum_extra.getItems();
                    column.graph_configuration =
                            this.format.val() == "graph" ? this.graph_extra.val() : null;
                    column.late_flag = parseInt(this.late_flag_extra.val(), 10);
                    column.time_ago_interval = parseFloat(this.time_ago_extra.val());
                    column.filter_xpath = this.filter_xpath_extra.val();
                    column.calc_xpath = this.calc_xpath_extra.val();
                    column.case_tile_field = this.case_tile_field();
                    if (this.isTab) {
                        // Note: starting_index is added by Screen.serialize
                        return _.extend({
                            starting_index: this.starting_index,
                            has_nodeset: column.hasNodeset,
                        }, _.pick(column, ['header', 'isTab', 'nodeset']));
                    }
                    return column;
                },
                setGrip: function (grip) {
                    this.grip = grip;
                },
                copyCallback: function () {
                    var column = this.serialize();
                    // add a marker that this is copied for this purpose
                    return JSON.stringify({
                        type: 'detail-screen-config:Column',
                        contents: column
                    });
                }
            };
            return Column;
        }());
        Screen = (function () {
            /**
             * The Screen "Class" is in charge inserting a table into the DOM that
             * contains rows for each case DetailColumn. It also handles the
             * reordering of these columns through drag and drop as well as
             * saving them on the server.
             * @param $home jQuery object where the Screen will be rendered
             * @param spec
             * @param config A DetailScreenConfig object.
             * @param options
             * @constructor
             */
            function Screen(spec, config, options) {
                var i, column, model, property, header,
                    that = this, columns;
                eventize(this);
                this.type = spec.type;
                this.saveUrl = options.saveUrl;
                this.config = config;
                this.columns = ko.observableArray([]);
                this.model = config.model;
                this.lang = options.lang;
                this.langs = options.langs || [];
                this.properties = options.properties;
                this.childCaseTypes = options.childCaseTypes;
                this.fixtures = options.fixtures;
                // The column key is used to retrieve the columns from the spec and
                // as the name of the key in the data object that is sent to the
                // server on save.
                this.columnKey = options.columnKey;
                // Not all Screen instances will handle sorting, parent selection,
                // and filtering. E.g The "Case Detail" tab only handles the module's
                // "long" case details. These flags will make sure this instance
                // doesn't try to save these configurations if it is not in charge
                // of these configurations.
                this.containsSortConfiguration = options.containsSortConfiguration;
                this.containsParentConfiguration = options.containsParentConfiguration;
                this.containsFixtureConfiguration = options.containsFixtureConfiguration;
                this.containsFilterConfiguration = options.containsFilterConfiguration;
                this.containsCaseListLookupConfiguration = options.containsCaseListLookupConfiguration;
                this.containsSearchConfiguration = options.containsSearchConfiguration;
                this.containsCustomXMLConfiguration = options.containsCustomXMLConfiguration;
                this.allowsTabs = options.allowsTabs;
                this.useCaseTiles = ko.observable(spec[this.columnKey].use_case_tiles ? "yes" : "no");
                this.showCaseTileColumn = ko.computed(function () {
                    return that.useCaseTiles() === "yes" && COMMCAREHQ.toggleEnabled('CASE_LIST_TILE');
                });
                this.persistCaseContext = ko.observable(spec[this.columnKey].persist_case_context || false);
                this.persistentCaseContextXML = ko.observable(spec[this.columnKey].persistent_case_context_xml|| 'case_name');
                this.customVariablesViewModel = {
                    enabled: COMMCAREHQ.toggleEnabled('CASE_LIST_CUSTOM_VARIABLES'),
                    xml: ko.observable(spec[this.columnKey].custom_variables || ""),
                };
                this.customVariablesViewModel.xml.subscribe(function(){
                    that.fireChange();
                });
                this.persistTileOnForms = ko.observable(spec[this.columnKey].persist_tile_on_forms || false);
                this.enableTilePullDown = ko.observable(spec[this.columnKey].pull_down_tile || false);
                this.allowsEmptyColumns = options.allowsEmptyColumns;

                this.fireChange = function() {
                    that.fire('change');
                };

                this.initColumnAsColumn = function (column) {
                    column.model.setEdit(false);
                    column.field.setEdit(true);
                    column.header.setEdit(true);
                    column.format.setEdit(true);
                    column.enum_extra.setEdit(true);
                    column.late_flag_extra.setEdit(true);
                    column.filter_xpath_extra.setEdit(true);
                    column.calc_xpath_extra.setEdit(true);
                    column.time_ago_extra.setEdit(true);
                    column.setGrip(true);
                    column.on('change', that.fireChange);

                    column.field.on('change', function () {
                        column.header.val(getPropertyTitle(this.val()));
                        column.header.fire("change");
                    });
                    if (column.original.hasAutocomplete) {
                        module.CC_DETAIL_SCREEN.setUpAutocomplete(column.field, that.properties);
                    }
                    return column;
                };

                columns = spec[this.columnKey].columns;
                // Inject tabs into the columns list:
                var tabs = spec[this.columnKey].tabs || [];
                for (i = 0; i < tabs.length; i++){
                    columns.splice(
                        tabs[i].starting_index + i,
                        0,
                        _.extend({
                            hasNodeset: tabs[i].has_nodeset,
                        }, _.pick(tabs[i], ["header", "nodeset", "isTab"]))
                    );
                }
                if (this.columnKey === 'long') {
                    this.addTab = function(hasNodeset) {
                        var col = that.initColumnAsColumn(Column.init({
                            isTab: true,
                            hasNodeset: hasNodeset,
                            model: 'tab',
                        }, that));
                        that.columns.splice(0, 0, col);
                    };
                }

                // Filters are a type of DetailColumn on the server. Don't display
                // them with the other columns though
                columns = _.filter(columns, function(col){
                    return col.format != "filter";
                });

                // set up the columns
                for (i = 0; i < columns.length; i += 1) {
                    this.columns.push(Column.init(columns[i], this));
                    that.initColumnAsColumn(this.columns()[i]);
                }

                this.saveButton = COMMCAREHQ.SaveButton.init({
                    unsavedMessage: DetailScreenConfig.message.UNSAVED_MESSAGE,
                    save: function () {
                        that.save();
                    }
                });
                this.on('change', function () {
                    this.saveButton.fire('change');
                });
                this.useCaseTiles.subscribe(function(){
                    that.saveButton.fire('change');
                });
                this.persistCaseContext.subscribe(function(){
                    that.saveButton.fire('change');
                });
                this.persistentCaseContextXML.subscribe(function(){
                    that.saveButton.fire('change');
                });
                this.persistTileOnForms.subscribe(function(){
                    that.saveButton.fire('change');
                });
                this.enableTilePullDown.subscribe(function(){
                    that.saveButton.fire('change');
                });
                this.columns.subscribe(function () {
                    that.saveButton.fire('change');
                });
            }
            Screen.init = function (spec, config, options) {
                return new Screen(spec, config, options);
            };
            Screen.prototype = {
                save: function () {
                    var i;
                    //Only save if property names are valid
                    var containsTab = false;
                    var columns = this.columns();
                    for (i = 0; i < columns.length; i++){
                        var column = columns[i];
                        column.saveAttempted(true);
                        if (!column.isTab) {
                            if (column.showWarning()){
                                alert(gettext("There are errors in your property names"));
                                return;
                            }
                        } else {
                            if (column.showWarning()){
                                alert(gettext("There are errors in your tabs"));
                                return;
                            }
                            containsTab = true;
                        }
                    }
                    if (containsTab){
                        if (!columns[0].isTab) {
                            alert(gettext("All properties must be below a tab"));
                            return;
                        }
                    }

                    if (this.containsSortConfiguration) {
                        var sortRows = this.config.sortRows.sortRows();
                        for (i = 0; i < sortRows.length; i++) {
                            var row = sortRows[i];
                            if (!row.hasValidPropertyName()) {
                                row.showWarning(true);
                            }
                        }
                    }
                    if (this.validate()){
                        this.saveButton.ajax({
                            url: this.saveUrl,
                            type: "POST",
                            data: this.serialize(),
                            dataType: 'json',
                            success: function (data) {
                                var app_manager = hqImport('app_manager/js/app_manager.js');
                                app_manager.updateDOM(data.update);
                            }
                        });
                    }
                },
                validate: function(){
                    if (this.containsCaseListLookupConfiguration){
                        return this.config.caseListLookup.validate();
                    }
                    return true;
                },
                serialize: function () {
                    var columns = this.columns();
                    var data = {
                        type: JSON.stringify(this.type)
                    };

                    // Add columns
                    data[this.columnKey] = JSON.stringify(_.map(
                        _.filter(columns, function(c){return ! c.isTab;}),
                        function(c){return c.serialize();}
                    ));

                    // Add tabs
                    // calculate the starting index for each Tab
                    var acc = 0;
                    for (var j = 0; j < columns.length; j++) {
                        var c = columns[j];
                        if (c.isTab){
                            c.starting_index = acc;
                        } else {
                            acc++;
                        }
                    }
                    data.tabs = JSON.stringify(_.map(
                        _.filter(columns, function(c){return c.isTab;}),
                        function(c){return c.serialize();}
                    ));

                    data.useCaseTiles = this.useCaseTiles() === "yes" ? true : false;
                    data.persistCaseContext = this.persistCaseContext();
                    data.persistentCaseContextXML = this.persistentCaseContextXML();
                    data.persistTileOnForms = this.persistTileOnForms();
                    data.enableTilePullDown = this.persistTileOnForms() ? this.enableTilePullDown() : false;

                    if (this.containsParentConfiguration) {
                        var parentSelect;
                        if (this.config.hasOwnProperty('parentSelect')) {
                            parentSelect = {
                                module_id: this.config.parentSelect.moduleId(),
                                relationship: 'parent',
                                active: this.config.parentSelect.active()
                            };
                        }
                        data.parent_select = JSON.stringify(parentSelect);
                    }
                    if (this.containsFixtureConfiguration) {
                        var fixtureSelect;
                        if (this.config.hasOwnProperty('fixtureSelect')) {
                            fixtureSelect = {
                                active: this.config.fixtureSelect.active(),
                                fixture_type: this.config.fixtureSelect.fixtureType(),
                                display_column: this.config.fixtureSelect.displayColumn(),
                                localize: this.config.fixtureSelect.localize(),
                                variable_column: this.config.fixtureSelect.variableColumn(),
                                xpath: this.config.fixtureSelect.xpath()
                            };
                        }
                        data.fixture_select = JSON.stringify(fixtureSelect);
                    }
                    if (this.containsSortConfiguration) {
                        data.sort_elements = JSON.stringify(_.map(this.config.sortRows.sortRows(), function(row){
                            return {
                                field: row.textField.val(),
                                type: row.type(),
                                direction: row.direction(),
                                display: row.display(),
                            };
                        }));
                    }
                    if (this.containsFilterConfiguration) {
                        data.filter = JSON.stringify(this.config.filter.serialize());
                    }
                    if (this.containsCaseListLookupConfiguration){
                        data.case_list_lookup = JSON.stringify(this.config.caseListLookup.serialize());
                    }
                    if (this.containsCustomXMLConfiguration){
                        data.custom_xml = this.config.customXMLViewModel.xml();
                    }
                    data[this.columnKey + '_custom_variables'] = this.customVariablesViewModel.xml();
                    if (this.containsSearchConfiguration) {
                        data.search_properties = JSON.stringify(this.config.search.serialize());
                    }
                    return data;
                },
                addItem: function (columnConfiguration, index) {
                    var column = this.initColumnAsColumn(
                        Column.init(columnConfiguration, this)
                    );
                    if (index === undefined) {
                        this.columns.push(column);
                    } else {
                        this.columns.splice(index, 0, column);
                    }
                },
                pasteCallback: function (data, index) {
                    try {
                         data = JSON.parse(data);
                    } catch (e) {
                        // just ignore pasting non-json
                        return;
                    }
                    if (data.type === 'detail-screen-config:Column' && data.contents) {
                        this.addItem(data.contents, index);
                    }
                },
                addProperty: function () {
                    var type = this.columnKey === "short" ? "List" : "Detail";
                    ga_track_event('Case Management', 'Module Level Case ' + type, 'Add Property');
                    this.addItem({hasAutocomplete: true});
                },
                addCalculation: function () {
                    this.addItem({hasAutocomplete: false, format: 'calculate'});
                },
                addGraph: function () {
                    this.addItem({hasAutocomplete: false, format: 'graph'});
                }
            };
            return Screen;
        }());
        DetailScreenConfig = (function () {
            var DetailScreenConfig = function (spec) {
                var that = this;
                this.properties = spec.properties;
                this.screens = [];
                this.model = spec.model || 'case';
                this.lang = spec.lang;
                this.langs = spec.langs || [];
                this.multimedia = spec.multimedia || {};
                this.module_id = spec.module_id || '';
                if (spec.hasOwnProperty('parentSelect') && spec.parentSelect) {
                    this.parentSelect = new module.ParentSelect({
                        active: spec.parentSelect.active,
                        moduleId: spec.parentSelect.module_id,
                        parentModules: spec.parentModules,
                        lang: this.lang,
                        langs: this.langs
                    });
                }

                if (spec.hasOwnProperty('fixtureSelect') && spec.fixtureSelect) {
                    this.fixtureSelect = new FixtureSelect({
                        active: spec.fixtureSelect.active,
                        fixtureType: spec.fixtureSelect.fixture_type,
                        displayColumn: spec.fixtureSelect.display_column,
                        localize: spec.fixtureSelect.localize,
                        variableColumn: spec.fixtureSelect.variable_column,
                        xpath: spec.fixtureSelect.xpath,
                        fixture_columns_by_type: spec.fixture_columns_by_type,
                    });
                }
                this.saveUrl = spec.saveUrl;
                this.contextVariables = spec.contextVariables;

                /**
                 * Add a Screen to this DetailScreenConfig
                 * @param pair
                 * @param columnType
                 * The type of case properties that this Screen will be displaying,
                 * either "short" or "long".
                 */
                function addScreen(pair, columnType) {

                    var screen = Screen.init(
                        pair,
                        that,
                        {
                            lang: that.lang,
                            langs: that.langs,
                            properties: that.properties,
                            saveUrl: that.saveUrl,
                            columnKey: columnType,
                            childCaseTypes: spec.childCaseTypes,
                            fixtures: _.keys(spec.fixture_columns_by_type),
                            containsSortConfiguration: columnType == "short",
                            containsParentConfiguration: columnType == "short",
                            containsFixtureConfiguration: (columnType == "short" && COMMCAREHQ.toggleEnabled('FIXTURE_CASE_SELECTION')),
                            containsFilterConfiguration: columnType == "short",
                            containsCaseListLookupConfiguration: (columnType == "short" && COMMCAREHQ.toggleEnabled('CASE_LIST_LOOKUP')),
                            // TODO: Check case_search_enabled_for_domain(), not toggle. FB 225343
                            containsSearchConfiguration: (columnType === "short" && COMMCAREHQ.toggleEnabled('SYNC_SEARCH_CASE_CLAIM')),
                            containsCustomXMLConfiguration: columnType == "short",
                            allowsTabs: columnType == 'long',
                            allowsEmptyColumns: columnType == 'long'
                        }
                    );
                    that.screens.push(screen);
                    return screen;
                }

                if (spec.state.short !== undefined) {
                    this.shortScreen = addScreen(spec.state, "short");
                    // Set up filter
                    var filter_xpath = spec.state.short.filter;
                    this.filter = new filterViewModel(filter_xpath ? filter_xpath : null, this.shortScreen.saveButton);
                    // Set up SortRows
                    this.sortRows = new SortRows(this.properties, this.shortScreen.saveButton);
                    if (spec.sortRows) {
                        for (var j = 0; j < spec.sortRows.length; j++) {
                            this.sortRows.addSortRow(
                                spec.sortRows[j].field,
                                spec.sortRows[j].type,
                                spec.sortRows[j].direction,
                                spec.sortRows[j].display[this.lang],
                                false
                            );
                        }
                    }
                    this.customXMLViewModel = {
                        enabled: COMMCAREHQ.toggleEnabled('CASE_LIST_CUSTOM_XML'),
                        xml: ko.observable(spec.state.short.custom_xml || "")
                    };
                    this.customXMLViewModel.xml.subscribe(function(v){
                        that.shortScreen.saveButton.fire("change");
                    });
                    var $case_list_lookup_el = $("#" + spec.state.type + "-list-callout-configuration");
                    this.caseListLookup = new caseListLookupViewModel(
                        $case_list_lookup_el,
                        spec.state.short,
                        spec.lang,
                        this.shortScreen.saveButton
                    );
                    // Set up case search
                    this.search = new searchViewModel(
                        spec.searchProperties || [],
                        spec.includeClosed,
                        spec.defaultProperties,
                        spec.lang,
                        this.shortScreen.saveButton
                    );
                }
                if (spec.state.long !== undefined) {
                    this.longScreen = addScreen(spec.state, "long");
                }
            };
            DetailScreenConfig.init = function (spec) {
                return new DetailScreenConfig(spec);
            };
            return DetailScreenConfig;
        }());

        DetailScreenConfig.message = {

            FIELD: gettext('Property'),
            HEADER: gettext('Display Text'),
            FORMAT: gettext('Format'),

            PLAIN_FORMAT: gettext('Plain'),
            DATE_FORMAT: gettext('Date'),
            TIME_AGO_FORMAT: gettext('Time Since or Until Date'),
            TIME_AGO_EXTRA_LABEL: gettext(' Measuring '),
            TIME_AGO_INTERVAL: {
                YEARS: gettext('Years since date'),
                MONTHS: gettext('Months since date'),
                WEEKS: gettext('Weeks since date'),
                DAYS: gettext('Days since date'),
                DAYS_UNTIL: gettext('Days until date'),
                WEEKS_UNTIL: gettext('Weeks until date'),
                MONTHS_UNTIL: gettext('Months until date'),
            },
            PHONE_FORMAT: gettext('Phone Number'),
            ENUM_FORMAT: gettext('ID Mapping'),
            ENUM_IMAGE_FORMAT: gettext('Icon'),
            ENUM_EXTRA_LABEL: gettext('Mapping: '),
            LATE_FLAG_FORMAT: gettext('Late Flag'),
            LATE_FLAG_EXTRA_LABEL: gettext(' Days late '),
            FILTER_XPATH_EXTRA_LABEL: '',
            INVISIBLE_FORMAT: gettext('Search Only'),
            ADDRESS_FORMAT: gettext('Address'),
            PICTURE_FORMAT: gettext('Picture'),
            AUDIO_FORMAT: gettext('Audio'),
            CALC_XPATH_FORMAT: gettext('Calculate'),
            CALC_XPATH_EXTRA_LABEL: '',
            DISTANCE_FORMAT: gettext('Distance from current location'),

            ADD_COLUMN: gettext('Add to list'),
            COPY_COLUMN: gettext('Duplicate'),
            DELETE_COLUMN: gettext('Delete'),

            UNSAVED_MESSAGE: gettext('You have unsaved detail screen configurations.'),
        };

        DetailScreenConfig.TIME_AGO = {
            year: 365.25,
            month: 365.25 / 12,
            week: 7,
            day: 1
        };

        DetailScreenConfig.MENU_OPTIONS = [
            {value: "plain", label: DetailScreenConfig.message.PLAIN_FORMAT},
            {value: "date", label: DetailScreenConfig.message.DATE_FORMAT},
            {value: "time-ago", label: DetailScreenConfig.message.TIME_AGO_FORMAT},
            {value: "phone", label: DetailScreenConfig.message.PHONE_FORMAT},
            {value: "enum", label: DetailScreenConfig.message.ENUM_FORMAT},
            {value: "late-flag", label: DetailScreenConfig.message.LATE_FLAG_FORMAT},
            {value: "invisible", label: DetailScreenConfig.message.INVISIBLE_FORMAT},
            {value: "address", label: DetailScreenConfig.message.ADDRESS_FORMAT},
            {value: "distance", label: DetailScreenConfig.message.DISTANCE_FORMAT}
        ];

        if (COMMCAREHQ.toggleEnabled('MM_CASE_PROPERTIES')) {
            DetailScreenConfig.MENU_OPTIONS.push(
                {value: "picture", label: DetailScreenConfig.message.PICTURE_FORMAT},
                {value: "audio", label: DetailScreenConfig.message.AUDIO_FORMAT}
            );
        }

        if (COMMCAREHQ.previewEnabled('ENUM_IMAGE')) {
            DetailScreenConfig.MENU_OPTIONS.push(
                {value: "enum-image", label: DetailScreenConfig.message.ENUM_IMAGE_FORMAT + gettext(' (Preview!)')}
            );
        }

        if (COMMCAREHQ.previewEnabled('CALC_XPATHS')) {
            DetailScreenConfig.MENU_OPTIONS.push(
                {value: "calculate", label: DetailScreenConfig.message.CALC_XPATH_FORMAT + gettext(' (Preview!)')}
            );
        }

        DetailScreenConfig.field_format_warning_message = gettext("Must begin with a letter and contain only letters, numbers, '-', and '_'");

        DetailScreenConfig.field_val_re = new RegExp(
            '^(' + word + ':)*(' + word + '\\/)*#?' + word + '$'
        );

        return DetailScreenConfig;
    }());

    /* for sharing variables between essentially separate parts of the ui */
    module.state = {
        requires_case_details: ko.observable()
    };
    return module;

});

ko.bindingHandlers.DetailScreenConfig_notifyShortScreenOnChange = {
    init: function (element, valueAccessor) {
        var $root = valueAccessor();
        setTimeout(function () {
            $(element).on('change', '*', function () {
                $root.shortScreen.fire('change');
            });
        }, 0);
    }
};

ko.bindingHandlers.addSaveButtonListener = {
    init: function(element, valueAccessor, allBindings, viewModel, bindingContext){
        bindingContext.$parent.initSaveButtonListeners($(element).parent());
    }
};

// http://www.knockmeout.net/2011/05/dragging-dropping-and-sorting-with.html
// connect items with observableArrays
ko.bindingHandlers.sortableList = {
    init: function(element, valueAccessor) {
        var list = valueAccessor();
        $(element).sortable({
            handle: '.grip',
            cursor: 'move',
            update: function(event, ui) {
                //retrieve our actual data item
                var item = ko.dataFor(ui.item.get(0));
                //figure out its new position
                var position = ko.utils.arrayIndexOf(ui.item.parent().children(), ui.item[0]);
                //remove the item and add it back in the right spot
                if (position >= 0) {
                    list.remove(item);
                    list.splice(position, 0, item);
                }
                ui.item.remove();
                item.notifyButton();
            }
        });
    }
};
