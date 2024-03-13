hqDefine("app_manager/js/details/case_claim", function () {
    var get = hqImport('hqwebapp/js/initial_page_data').get,
        generateSemiRandomId = function () {
            // https://stackoverflow.com/a/2117523
            return ([1e7] + -1e3 + -4e3 + -8e3 + -1e11).replace(/[018]/g, function (c) {
                return (c ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> c / 4).toString(16);
            });
        },
        subscribeToSave = function (model, observableNames, saveButton) {
            _.each(observableNames, function (name) {
                model[name].subscribe(function () {
                    saveButton.fire('change');
                });
            });
            $(".hq-help").hqHelp();
        },
        itemsetValue = function (item) {
            return "instance('" + item.id + "')" + item.path;
        };

    var itemsetModel = function (options, saveButton) {
        options = _.defaults(options, {
            'instance_id': '',
            'nodeset': null,
            'label': '',
            'value': '',
            'sort': '',
        });
        var self = ko.mapping.fromJS(options);

        self.lookupTableNodeset = ko.pureComputed({
            write: function (value) {
                if (value === undefined) {
                    self.nodeset(null);
                } else {
                    self.instance_id(value);
                    var itemList = _.filter(get('js_options').item_lists, function (item) {
                        return item.id === value;
                    });
                    if (itemList && itemList.length === 1) {
                        self.nodeset(itemsetValue(itemList[0]));
                    } else {
                        self.nodeset(null);
                    }
                }
            },
            read: function () {
                return self.instance_id();
            },
        });
        self.nodesetValid = ko.computed(function () {
            if (self.nodeset() === null) {
                return true;
            }
            var itemLists = _.map(get('js_options').item_lists, function (item) {
                return itemsetValue(item);
            });
            if (self.nodeset().split("/").length === 0) {
                return false;
            }
            var instancePart = self.nodeset().split("/")[0];
            for (var i = itemLists.length - 1; i >= 0; i--) {
                var groups = itemLists[i].split("/");
                if (groups.length > 0 && groups[0] === instancePart) {
                    return true;
                }
            }
            return false;
        });
        subscribeToSave(self,
            ['nodeset', 'label', 'value', 'sort'], saveButton);

        return self;
    };

    var searchPropertyModel = function (options, saveButton) {
        options = _.defaults(options, {
            name: '',
            label: '',
            hint: '',
            appearance: '',
            isMultiselect: false,
            allowBlankValue: false,
            defaultValue: '',
            hidden: false,
            receiverExpression: '',
            itemsetOptions: {},
            exclude: false,
            requiredTest: '',
            requiredText: '',
            validationTest: '',
            validationText: '',
            isGroup: false,
            groupKey: '',
        });
        var self = {};
        self.uniqueId = generateSemiRandomId();
        self.name = ko.observable(options.name);
        self.label = ko.observable(options.label);
        self.hint = ko.observable(options.hint);
        self.appearance = ko.observable(options.appearance);
        self.isMultiselect = ko.observable(options.isMultiselect);
        self.allowBlankValue = ko.observable(options.allowBlankValue);
        self.defaultValue = ko.observable(options.defaultValue);
        self.hidden = ko.observable(options.hidden);
        self.exclude = ko.observable(options.exclude);
        self.requiredTest = ko.observable(options.requiredTest);
        self.requiredText = ko.observable(options.requiredText);
        self.validationTest = ko.observable(options.validationTest);
        self.validationText = ko.observable(options.validationText);
        self.appearanceFinal = ko.computed(function () {
            var appearance = self.appearance();
            if (appearance === 'report_fixture' || appearance === 'lookup_table_fixture') {
                return 'fixture';
            } else {
                return appearance;
            }
        });
        self.dropdownLabels = ko.computed(function () {
            if (self.appearance() === 'report_fixture') {
                return {
                    'labelPlaceholder': 'column_0',
                    'valuePlaceholder': 'column_0',
                    'optionsLabel': gettext("Mobile UCR Options"),
                    'tableLabel': gettext("Mobile UCR Report"),
                    'selectLabel': gettext("Select a Report..."),
                };
            } else {
                return {
                    'labelPlaceholder': 'name',
                    'valuePlaceholder': 'id',
                    'optionsLabel': gettext("Lookup Table Options"),
                    'tableLabel': gettext("Lookup Table"),
                    'selectLabel': gettext("Select a Lookup Table..."),
                };
            }
        });

        self.receiverExpression = ko.observable(options.receiverExpression);
        self.itemListOptions = ko.computed(function () {
            var itemLists = get('js_options').item_lists;
            return _.map(
                _.filter(itemLists, function (p) {
                    return (
                        p.fixture_type === self.appearance()
                        || (p.fixture_type === 'lookup_table_fixture' && self.appearance() === 'checkbox')
                    );
                }),
                function (p) {
                    return {
                        "value": p.id,
                        "name": p.name,
                    };
                }
            );
        });
        self.itemset = itemsetModel(options.itemsetOptions, saveButton);
        self.isGroup = options.isGroup;
        self.groupKey = options.groupKey;

        subscribeToSave(self, [
            'name', 'label', 'hint', 'appearance', 'defaultValue', 'hidden',
            'receiverExpression', 'isMultiselect', 'allowBlankValue', 'exclude',
            'requiredTest', 'requiredText', 'validationTest', 'validationText',
        ], saveButton);
        return self;
    };

    var defaultPropertyModel = function (options, saveButton) {
        options = _.defaults(options, {
            property: '',
            defaultValue: '',
        });
        var self = ko.mapping.fromJS(options);

        subscribeToSave(self, ['property', 'defaultValue'], saveButton);

        return self;
    };

    var customSortPropertyModel = function (options, saveButton) {
        options = _.defaults(options, {
            property_name: '',
            sort_type: '',
            direction: '',
        });
        var self = ko.mapping.fromJS(options);

        subscribeToSave(self, ['property_name', 'sort_type', 'direction'], saveButton);
        return self;
    };

    var additionalRegistryCaseModel = function (xpath, saveButton) {
        var self = {};
        self.uniqueId = generateSemiRandomId();
        self.caseIdXpath = ko.observable(xpath || '');
        subscribeToSave(self, ['caseIdXpath'], saveButton);
        return self;
    };

    var searchConfigKeys = [
        'auto_launch', 'blacklisted_owner_ids_expression', 'default_search', 'search_again_label',
        'title_label', 'description', 'search_button_display_condition', 'search_label', 'search_filter',
        'additional_relevant', 'data_registry', 'data_registry_workflow', 'additional_registry_cases',
        'custom_related_case_property', 'inline_search', 'instance_name', 'include_all_related_cases',
        'search_on_clear',
    ];
    var searchConfigModel = function (options, lang, searchFilterObservable, saveButton) {
        hqImport("hqwebapp/js/assert_properties").assertRequired(options, searchConfigKeys);

        options.search_label = options.search_label[lang] || "";
        options.search_again_label = options.search_again_label[lang] || "";
        options.title_label = options.title_label[lang] || "";
        options.description = options.description[lang] || "";
        var mapping = {
            'additional_registry_cases': {
                create: function (options) {
                    return additionalRegistryCaseModel(options.data, saveButton);
                },
            },
        };
        var self = ko.mapping.fromJS(options, mapping);

        self.restrictWorkflowForDataRegistry = ko.pureComputed(() => {
            return self.data_registry() && self.data_registry_workflow() === 'load_case';
        });

        self.workflow = ko.computed({
            read: function () {
                if (self.restrictWorkflowForDataRegistry()) {
                    if (self.auto_launch()) {
                        if (self.default_search()) {
                            return "es_only";
                        }
                    }
                    return "auto_launch";
                }
                if (self.auto_launch()) {
                    if (self.default_search()) {
                        return "es_only";
                    }
                    return "auto_launch";
                } else if (self.default_search()) {
                    return "see_more";
                }
                return "classic";
            },
            write: function (value) {
                self.auto_launch(_.contains(["es_only", "auto_launch"], value));
                self.default_search(_.contains(["es_only", "see_more"], value));
            },
        });

        self.inlineSearchVisible = ko.computed(() => {
            return self.workflow() === "es_only" || self.workflow() === "auto_launch";
        });

        self.inlineSearchActive = ko.computed(() => {
            return self.inlineSearchVisible() && self.inline_search();
        });
        self.exampleInstance = ko.computed(() => {
            let name = self.instance_name() || 'inline';
            return "instance('results:" + name + "')/results/case";
        });


        // Allow search filter to be copied from another part of the page
        self.setSearchFilterVisible = ko.computed(function () {
            return searchFilterObservable && searchFilterObservable();
        });
        self.setSearchFilterEnabled = ko.computed(function () {
            return self.setSearchFilterVisible() && searchFilterObservable() !== self.search_filter();
        });
        self.setSearchFilter = function () {
            self.search_filter(searchFilterObservable());
        };

        subscribeToSave(self, searchConfigKeys, saveButton);
        // media image/audio buttons
        $(".case-search-multimedia-input button").on("click", function () {
            saveButton.fire('change');
        });
        // checkbox to select media for all languages
        $(".case-search-multimedia-input input[type='checkbox']").on('change', function () {
            saveButton.fire('change');
        });

        self.addRegistryQuery = function () {
            self.additional_registry_cases.push(additionalRegistryCaseModel('', saveButton));
        };

        self.removeRegistryQuery = function (model) {
            self.additional_registry_cases.remove(model);
        };

        self.serialize = function () {
            var data = ko.mapping.toJS(self);
            data.additional_registry_cases = data.data_registry_workflow === "load_case" ? _.pluck(data.additional_registry_cases, 'caseIdXpath') : [];
            _.each(['search_label', 'search_again_label'], function (label) {
                _.each(['image', 'audio'], function (media) {
                    var key = label + "_" + media,
                        selector = "#case_search-" + label + "_media_media_" + media + " input[type='hidden']";
                    data[key] = $(selector + "[name='case_search-" + label + "_media_media_" + media + "']").val();
                    data[key + "_for_all"] = $(selector + "[name='case_search-" + label + "_media_use_default_" + media + "_for_all']").val();
                });
            });
            return data;
        };

        return self;
    };

    var _getAppearance = function (searchProperty) {
        // init with blank string to avoid triggering save button
        var appearance = searchProperty.appearance || "";
        if (searchProperty.input_ === "select1" || searchProperty.input_ === "select") {
            var instanceId = searchProperty.itemset.instance_id;
            if (instanceId !== null && instanceId.includes("commcare-reports")) {
                appearance = "report_fixture";
            } else {
                appearance = "lookup_table_fixture";
            }
        }
        if (searchProperty.appearance === "address") {
            appearance = "address";
        }
        if (["date", "daterange", "checkbox"].indexOf(searchProperty.input_) !== -1) {
            appearance = searchProperty.input_;
        }
        return appearance;
    };

    var searchViewModel = function (searchProperties, defaultProperties, customSortProperties, searchConfigOptions, lang, saveButton, searchFilterObservable) {
        var self = {};

        self.searchConfig = searchConfigModel(searchConfigOptions, lang, searchFilterObservable, saveButton);
        self.default_properties = ko.observableArray();
        self.custom_sort_properties = ko.observableArray();

        // searchProperties is a list of CaseSearchProperty objects
        var wrappedSearchProperties = _.map(searchProperties, function (searchProperty) {
            // The model supports multiple validation conditions, but we don't need the UI for it yet
            var validation = searchProperty.validations[0];
            return searchPropertyModel({
                name: searchProperty.name,
                label: searchProperty.label[lang],
                hint: searchProperty.hint[lang],
                appearance: _getAppearance(searchProperty),
                isMultiselect: searchProperty.input_ === "select",
                allowBlankValue: searchProperty.allow_blank_value,
                exclude: searchProperty.exclude,
                requiredTest: searchProperty.required.test,
                requiredText: searchProperty.required.text[lang],
                validationTest: validation ? validation.test : '',
                validationText: validation ? validation.text[lang] : '',
                defaultValue: searchProperty.default_value,
                hidden: searchProperty.hidden,
                receiverExpression: searchProperty.receiver_expression,
                itemsetOptions: searchProperty.itemset,
                isGroup: searchProperty.is_group,
                groupKey: searchProperty.group_key,
            }, saveButton);
        });

        self.search_properties = ko.observableArray(
            wrappedSearchProperties.length > 0 ? wrappedSearchProperties : [searchPropertyModel({}, saveButton)]
        );

        self.search_properties.subscribe(function (newProperties) {
            let groupKey = '';
            ko.utils.arrayForEach(newProperties, function (property, index) {
                if (property.isGroup) {
                    groupKey = `group_header_${index}`;
                    if (property.name !== groupKey) {
                        property.name(groupKey);
                    }
                }
                if (property.groupKey !== groupKey) {
                    property.groupKey = groupKey;
                }
            });
        });

        self.addProperty = function () {
            self.search_properties.push(searchPropertyModel({}, saveButton));
        };
        self.addGroupProperty = function () {
            self.search_properties.push(searchPropertyModel({isGroup: true}, saveButton));
        };
        self.removeProperty = function (property) {
            self.search_properties.remove(property);
        };
        self._getProperties = function () {
            // i.e. [{'name': p.name, 'label': p.label} for p in self.search_properties if p.name]
            return _.map(
                _.filter(
                    self.search_properties(),
                    function (p) { return p.name().length > 0;}  // Skip properties where name is blank
                ),
                function (p) {
                    var ifSupportsValidation = function (val) {
                        return p.hidden() || p.appearance() === "address" ? "" : val;
                    };
                    return {
                        name: p.name(),
                        label: (p.label().length || p.isGroup) ? p.label() : p.name(),  // If label isn't set, use name
                        hint: p.hint(),
                        appearance: p.appearanceFinal(),
                        is_multiselect: p.isMultiselect(),
                        allow_blank_value: p.allowBlankValue(),
                        exclude: p.exclude(),
                        required_test: ifSupportsValidation(p.requiredTest()),
                        required_text: ifSupportsValidation(p.requiredText()),
                        validation_test: ifSupportsValidation(p.validationTest()),
                        validation_text: ifSupportsValidation(p.validationText()),
                        default_value: p.defaultValue(),
                        hidden: p.hidden(),
                        receiver_expression: p.receiverExpression(),
                        fixture: ko.toJSON(p.itemset),
                        is_group: p.isGroup,
                        group_key: p.groupKey,
                    };
                }
            );
        };

        self.addDefaultProperty = function () {
            self.default_properties.push(defaultPropertyModel({}, saveButton));
        };
        self.removeDefaultProperty = function (property) {
            self.default_properties.remove(property);
        };
        self._getDefaultProperties = function () {
            return _.map(
                _.filter(
                    self.default_properties(),
                    function (p) { return p.property().length > 0; }  // Skip properties where property is blank
                ),
                function (prop) { return ko.mapping.toJS(prop); }
            );
        };

        self.addCustomSortProperty = function () {
            self.custom_sort_properties.push(customSortPropertyModel({}, saveButton));
        };
        self.removeCustomSortProperty = function (property) {
            self.custom_sort_properties.remove(property);
        };
        self._getCustomSortProperties = function () {
            return _.map(
                _.filter(
                    self.custom_sort_properties(),
                    // Skip properties where property is blank
                    function (p) { return p.property_name().length > 0; }
                ),
                function (prop) { return ko.mapping.toJS(prop); }
            );
        };

        if (defaultProperties.length > 0) {
            self.default_properties(_.map(defaultProperties, function (p) {
                return defaultPropertyModel(p, saveButton);
            }));
        } else {
            self.addDefaultProperty();
        }

        if (customSortProperties.length > 0) {
            self.custom_sort_properties(_.map(customSortProperties, function (p) {
                return customSortPropertyModel(p, saveButton);
            }));
        }

        self.commonProperties = ko.computed(function () {
            var defaultProperties = _.pluck(self._getDefaultProperties(), 'property');
            var commonProperties = self.search_properties().filter(function (n) {
                return n.name().length > 0 && defaultProperties.indexOf(n.name()) !== -1;
            });
            return _.map(
                commonProperties,
                function (p) {
                    return p.name();
                }
            );
        });

        self.isCommon = function (prop) {
            return self.commonProperties().indexOf(prop) !== -1;
        };

        self.isEnabled = ko.computed(() => {
            // match logic in corehq.apps.app_manager.util.module_offers_search
            return self._getProperties().length > 0 || self._getDefaultProperties().length > 0;
        });

        self.serialize = function () {
            return _.extend({
                properties: self._getProperties(),
                default_properties: self._getDefaultProperties(),
                custom_sort_properties: self._getCustomSortProperties(),
            }, self.searchConfig.serialize());
        };

        subscribeToSave(self, ['search_properties', 'default_properties', 'custom_sort_properties'], saveButton);
        return self;
    };

    return {
        searchConfigKeys: searchConfigKeys,
        searchViewModel: searchViewModel,
    };
});
