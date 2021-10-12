/* global Uint8Array */
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
            'instance_uri': '',
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
                }
                else {
                    self.instance_id(value);
                    var itemList = _.filter(get('js_options').item_lists, function (item) {
                        return item.id === value;
                    });
                    if (itemList && itemList.length === 1) {
                        self.instance_uri(itemList[0]['uri']);
                        self.nodeset(itemsetValue(itemList[0]));
                    }
                    else {
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
            ['nodeset', 'label', 'value', 'sort', 'instance_uri'], saveButton);

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
        self.appearanceFinal = ko.computed(function () {
            var appearance = self.appearance();
            if (appearance === 'report_fixture' || appearance === 'lookup_table_fixture') {
                return 'fixture';
            }
            else {
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
                    'advancedLabel': gettext("Advanced Mobile UCR Options"),
                };
            }
            else {
                return {
                    'labelPlaceholder': 'name',
                    'valuePlaceholder': 'id',
                    'optionsLabel': gettext("Lookup Table Options"),
                    'tableLabel': gettext("Lookup Table"),
                    'selectLabel': gettext("Select a Lookup Table..."),
                    'advancedLabel': gettext("Advanced Lookup Table Options"),
                };
            }
        });

        self.receiverExpression = ko.observable(options.receiverExpression);
        self.itemListOptions = ko.computed(function () {
            var itemLists = get('js_options').item_lists;
            return _.map(
                _.filter(itemLists, function (p) {
                    return p.fixture_type === self.appearance();
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

        subscribeToSave(self, [
            'name', 'label', 'hint', 'appearance', 'defaultValue', 'hidden',
            'receiverExpression', 'isMultiselect', 'allowBlankValue',
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

    var additionalQueryModel = function (options, saveButton) {
        options = _.defaults(options, {
            instance_name: '',
            case_type_xpath: '',
            case_id_xpath: '',
        });
        var self = {};
        self.uniqueId = generateSemiRandomId();
        self.instanceName = ko.observable(options.instance_name);
        self.caseTypeXpath = ko.observable(options.case_type_xpath);
        self.caseIdXpath = ko.observable(options.case_id_xpath);
        subscribeToSave(self, ['instanceName', 'caseTypeXpath', 'caseIdXpath'], saveButton);
        return self;
    };

    var searchConfigKeys = [
        'autoLaunch', 'blacklistedOwnerIdsExpression', 'defaultSearch', 'searchAgainLabel',
        'searchButtonDisplayCondition', 'searchLabel', 'searchFilter', 'searchDefaultRelevant',
        'searchAdditionalRelevant', 'dataRegistry', 'dataRegistryWorkflow', 'additionalRegistryQueries',
    ];
    var searchConfigModel = function (options, lang, searchFilterObservable, saveButton) {
        hqImport("hqwebapp/js/assert_properties").assertRequired(options, searchConfigKeys);

        options.searchLabel = options.searchLabel[lang] || "";
        options.searchAgainLabel = options.searchAgainLabel[lang] || "";
        var mapping = {
            'additionalRegistryQueries': {
                create: function(options) {
                    return additionalQueryModel(options.data, saveButton);
                },
            },
        };
        var self = ko.mapping.fromJS(options, mapping);

        self.workflow = ko.computed({
            read: function () {
                if (self.autoLaunch()) {
                    if (self.defaultSearch()) {
                        return "es_only";
                    }
                    return "auto_launch";
                } else if (self.defaultSearch()) {
                    return "see_more";
                }
                return "classic";
            },
            write: function (value) {
                self.autoLaunch(_.contains(["es_only", "auto_launch"], value));
                self.defaultSearch(_.contains(["es_only", "see_more"], value));
            },
        });

        // Allow search filter to be copied from another part of the page
        self.setSearchFilterVisible = ko.computed(function () {
            return searchFilterObservable && searchFilterObservable();
        });
        self.setSearchFilterEnabled = ko.computed(function () {
            return self.setSearchFilterVisible() && searchFilterObservable() !== self.searchFilter();
        });
        self.setSearchFilter = function () {
            self.searchFilter(searchFilterObservable());
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
            self.additionalRegistryQueries.push(additionalQueryModel({}, saveButton));
        };

        self.removeRegistryQuery = function (query) {
            self.additionalRegistryQueries.remove(query);
        };

        self.serialize = function () {
            return {
                auto_launch: self.autoLaunch(),
                default_search: self.defaultSearch(),
                search_default_relevant: self.searchDefaultRelevant(),
                search_additional_relevant: self.searchAdditionalRelevant(),
                search_button_display_condition: self.searchButtonDisplayCondition(),
                data_registry: self.dataRegistry(),
                data_registry_workflow: self.dataRegistryWorkflow(),
                search_label: self.searchLabel(),
                search_label_image:
                    $("#case_search-search_label_media_media_image input[type=hidden][name='case_search-search_label_media_media_image']").val() || null,
                search_label_image_for_all:
                    $("#case_search-search_label_media_media_image input[type=hidden][name='case_search-search_label_media_use_default_image_for_all']").val() || null,
                search_label_audio:
                    $("#case_search-search_label_media_media_audio input[type=hidden][name='case_search-search_label_media_media_audio']").val() || null,
                search_label_audio_for_all:
                    $("#case_search-search_label_media_media_audio input[type=hidden][name='case_search-search_label_media_use_default_audio_for_all']").val() || null,
                search_again_label: self.searchAgainLabel(),
                search_again_label_image:
                    $("#case_search-search_again_label_media_media_image input[type=hidden][name='case_search-search_again_label_media_media_image']").val() || null,
                search_again_label_image_for_all:
                    $("#case_search-search_again_label_media_media_image input[type=hidden][name='case_search-search_again_label_media_use_default_image_for_all']").val() || null,
                search_again_label_audio:
                    $("#case_search-search_again_label_media_media_audio input[type=hidden][name='case_search-search_again_label_media_media_audio']").val() || null,
                search_again_label_audio_for_all:
                    $("#case_search-search_again_label_media_media_audio input[type=hidden][name='case_search-search_again_label_media_use_default_audio_for_all']").val() || null,
                search_filter: self.searchFilter(),
                blacklisted_owner_ids_expression: self.blacklistedOwnerIdsExpression(),
                additional_registry_queries: self.additionalRegistryQueries().map((query) => {
                    return {
                        instance_name: query.instanceName(),
                        case_type_xpath: query.caseTypeXpath(),
                        case_id_xpath: query.caseTypeXpath(),
                    };
                }),
            };
        };

        return self;
    };

    var searchViewModel = function (searchProperties, defaultProperties, searchConfigOptions, lang, saveButton, searchFilterObservable) {
        var self = {};

        self.searchConfig = searchConfigModel(searchConfigOptions, lang, searchFilterObservable, saveButton);
        self.searchProperties = ko.observableArray();
        self.defaultProperties = ko.observableArray();

        if (searchProperties.length > 0) {
            for (var i = 0; i < searchProperties.length; i++) {
                // searchProperties is a list of CaseSearchProperty objects
                // property labels/hints come in keyed by lang.
                var label = searchProperties[i].label[lang];
                var hint = searchProperties[i].hint[lang] || "";
                var appearance = searchProperties[i].appearance || "";  // init with blank string to avoid triggering save button
                if (searchProperties[i].input_ === "select1" || searchProperties[i].input_ === "select") {
                    var uri = searchProperties[i].itemset.instance_uri;
                    if (uri !== null && uri.includes("commcare-reports")) {
                        appearance = "report_fixture";
                    }
                    else {
                        appearance = "lookup_table_fixture";
                    }
                }
                if (searchProperties[i].appearance === "address") {
                    appearance = "address";
                }
                if (searchProperties[i].input_ === "daterange") {
                    appearance = "daterange";
                }
                var isMultiselect = searchProperties[i].input_ === "select";
                self.searchProperties.push(searchPropertyModel({
                    name: searchProperties[i].name,
                    label: label,
                    hint: hint,
                    appearance: appearance,
                    isMultiselect: isMultiselect,
                    allowBlankValue: searchProperties[i].allow_blank_value,
                    defaultValue: searchProperties[i].default_value,
                    hidden: searchProperties[i].hidden,
                    receiverExpression: searchProperties[i].receiver_expression,
                    itemsetOptions: {
                        instance_id: searchProperties[i].itemset.instance_id,
                        instance_uri: searchProperties[i].itemset.instance_uri,
                        nodeset: searchProperties[i].itemset.nodeset,
                        label: searchProperties[i].itemset.label,
                        value: searchProperties[i].itemset.value,
                        sort: searchProperties[i].itemset.sort,
                    },
                }, saveButton));
            }
        } else {
            self.searchProperties.push(searchPropertyModel({}, saveButton));
        }

        self.addProperty = function () {
            self.searchProperties.push(searchPropertyModel({}, saveButton));
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
                        hint: p.hint(),
                        appearance: p.appearanceFinal(),
                        is_multiselect: p.isMultiselect(),
                        allow_blank_value: p.allowBlankValue(),
                        default_value: p.defaultValue(),
                        hidden: p.hidden(),
                        receiver_expression: p.receiverExpression(),
                        fixture: ko.toJSON(p.itemset),
                    };
                }
            );
        };

        if (defaultProperties.length > 0) {
            for (var k = 0; k < defaultProperties.length; k++) {
                self.defaultProperties.push(defaultPropertyModel({
                    property: defaultProperties[k].property,
                    defaultValue: defaultProperties[k].defaultValue,
                }, saveButton));
            }
        } else {
            self.defaultProperties.push(defaultPropertyModel({}, saveButton));
        }
        self.addDefaultProperty = function () {
            self.defaultProperties.push(defaultPropertyModel({}, saveButton));
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

        self.commonProperties = ko.computed(function () {
            var defaultProperties = _.map(self._getDefaultProperties(), function (p) {
                return p.property;
            });
            var commonProperties = self.searchProperties().filter(function (n) {
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

        self.serialize = function () {
            return _.extend({
                properties: self._getProperties(),
                default_properties: self._getDefaultProperties(),
            }, self.searchConfig.serialize());
        };

        subscribeToSave(self, ['searchProperties', 'defaultProperties'], saveButton);

        return self;
    };

    return {
        searchConfigKeys: searchConfigKeys,
        searchViewModel: searchViewModel,
    };
});
