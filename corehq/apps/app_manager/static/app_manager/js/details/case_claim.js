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
        };

    var itemsetModel = function (options, saveButton) {
        options = _.defaults(options, {
            'instance_id': '',
            'instance_uri': '',
            'nodeset': '',
            'label': '',
            'value': '',
            'sort': '',
        });
        var self = ko.mapping.fromJS(options);

        self.lookupTableNodeset = ko.pureComputed({
            write: function (value) {
                self.nodeset(value);
                var reg = /instance\(['"]([\w\-:]+)['"]\)/g,
                    matches = reg.exec(value);
                if (matches && matches.length > 1) {
                    var instanceId = matches[1],
                        itemList = _.findWhere(get('js_options').item_lists, {'id': instanceId});

                    self.instance_id(instanceId);
                    if (itemList) {
                        self.instance_uri(itemList['uri']);
                    }
                }
            },
            read: function () {
                // is the nodeset a lookup table that we know about?
                var itemLists = get('js_options').item_lists,
                    itemListNodesets = _.map(itemLists, function (item) {
                        return "instance('" + item.id + "')" + item.path;
                    });
                if (itemListNodesets.indexOf(self.nodeset()) !== -1) {

                    return self.nodeset();
                } else {
                    return '';
                }
            },
        });

        subscribeToSave(self, ['nodeset', 'label', 'value', 'sort'], saveButton);

        return self;
    };

    var searchPropertyModel = function (options, saveButton) {
        options = _.defaults(options, {
            name: '',
            label: '',
            appearance: '',
            defaultValue: '',
            itemsetOptions: {},
        });
        var self = {};
        self.uniqueId = generateSemiRandomId();
        self.name = ko.observable(options.name);
        self.label = ko.observable(options.label);
        self.appearance = ko.observable(options.appearance);
        self.defaultValue = ko.observable(options.defaultValue);

        self.itemset = itemsetModel(options.itemsetOptions, saveButton);

        subscribeToSave(self, ['name', 'label', 'appearance', 'defaultValue'], saveButton);

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

    var searchConfigKeys = [
        'autoLaunch', 'blacklistedOwnerIdsExpression', 'defaultSearch', 'includeClosed', 'searchAgainLabel',
        'searchButtonDisplayCondition', 'searchCommandLabel', 'searchFilter', 'searchDefaultRelevant',
        'searchAdditionalRelevant', 'sessionVar',
    ];
    var searchConfigModel = function (options, lang, searchFilterObservable, saveButton) {
        hqImport("hqwebapp/js/assert_properties").assertRequired(options, searchConfigKeys);

        options.searchCommandLabel = options.searchCommandLabel[lang] || "";
        options.searchAgainLabel = options.searchAgainLabel[lang] || "";
        var self = ko.mapping.fromJS(options);

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

        self.serialize = function () {
            return {
                auto_launch: self.autoLaunch(),
                default_search: self.defaultSearch(),
                session_var: self.sessionVar(),
                search_default_relevant: self.searchDefaultRelevant(),
                search_additional_relevant: self.searchAdditionalRelevant(),
                search_button_display_condition: self.searchButtonDisplayCondition(),
                search_command_label: self.searchCommandLabel(),
                search_again_label: self.searchAgainLabel(),
                search_filter: self.searchFilter(),
                include_closed: self.includeClosed(),
                blacklisted_owner_ids_expression: self.blacklistedOwnerIdsExpression(),
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
                // property labels come in keyed by lang.
                var label = searchProperties[i].label[lang];
                var appearance = searchProperties[i].appearance || "";  // init with blank string to avoid triggering save button
                if (searchProperties[i].input_ === "select1") {
                    appearance = "fixture";
                }
                self.searchProperties.push(searchPropertyModel({
                    name: searchProperties[i].name,
                    label: label,
                    appearance: appearance,
                    defaultValue: searchProperties[i].default_value,
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
                        appearance: p.appearance(),
                        default_value: p.defaultValue(),
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
