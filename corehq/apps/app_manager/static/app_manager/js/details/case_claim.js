/* global Uint8Array */
hqDefine("app_manager/js/details/case_claim", function () {

    var get = hqImport('hqwebapp/js/initial_page_data').get,
        generateSemiRandomId = function () {
        // https://stackoverflow.com/a/2117523
            return ([1e7] + -1e3 + -4e3 + -8e3 + -1e11).replace(/[018]/g, function (c) {
                return (c ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> c / 4).toString(16);
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

        // Nodeset: if the nodeset is in the list,
        self.nodeset.subscribe(function () {
            saveButton.fire('change');
        });
        self.label.subscribe(function () {
            saveButton.fire('change');
        });
        self.value.subscribe(function () {
            saveButton.fire('change');
        });
        self.sort.subscribe(function () {
            saveButton.fire('change');
        });

        return self;
    };

    var searchPropertyModel = function (options, saveButton) {
        options = _.defaults(options, {
            name: '',
            label: '',
            appearance: '',
            itemsetOptions: {},
        });
        var self = {};
        self.uniqueId = generateSemiRandomId();
        self.name = ko.observable(options.name);
        self.label = ko.observable(options.label);
        self.appearance = ko.observable(options.appearance);

        self.itemset = itemsetModel(options.itemsetOptions, saveButton);

        self.name.subscribe(function () {
            saveButton.fire('change');
        });
        self.label.subscribe(function () {
            saveButton.fire('change');
        });
        self.appearance.subscribe(function () {
            saveButton.fire('change');
        });

        return self;
    };

    var defaultPropertyModel = function (options, saveButton) {
        options = _.defaults(options, {
            property: '',
            defaultValue: '',
        });
        var self = ko.mapping.fromJS(options);

        self.property.subscribe(function () {
            saveButton.fire('change');
        });
        self.defaultValue.subscribe(function () {
            saveButton.fire('change');
        });

        return self;
    };

    var searchConfigKeys = [
        'autoLaunch', 'blacklistedOwnerIdsExpression', 'defaultSearch', 'includeClosed', 'searchAgainLabel',
        'searchButtonDisplayCondition', 'searchCommandLabel', 'searchFilter', 'searchRelevant', 'sessionVar',
    ];
    var searchConfigModel = function(options) {
        hqImport("hqwebapp/js/assert_properties").assertRequired(options, searchConfigKeys);
        var self = _.extend({}, options);

        // TODO: move config behavior in here

        return self;
    };

    var searchViewModel = function (searchProperties, defaultProperties, searchConfig, lang, saveButton, searchFilterObservable) {
        var self = {},
            DEFAULT_CLAIM_RELEVANT = "count(instance('casedb')/casedb/case[@case_id=instance('commcaresession')/session/data/case_id]) = 0";

        self.getWorkflow = function (autoLaunch, defaultSearch) {
            if (autoLaunch) {
                if (defaultSearch) {
                    return "es_only";   // TODO: constants here, next function, and in HTML
                }
                return "auto_launch";
            } else if (defaultSearch) {
               return "see_more";
            }
            return "classic";
        };

        self.serializeWorkflow = function () {
            var options = {
                auto_launch: false,
                default_search: false,
            };
            if (_.contains(["es_only", "autolaunch"], self.searchWorkflow())) {
                options.auto_launch = true;
            }
            if (_.contains(["es_only", "see_more"], self.searchWorkflow())) {
                options.default_search = true;
            }
            return options;
        };

        // Many search config atributes map directly to observables
        var searchConfigObservableKeys = _.without(searchConfigKeys, ['autoLaunch', 'defaultSearch', 'searchRelevant']);
        _.each(searchConfigObservableKeys, function (key) {
            var initialValue = searchConfig[key];
            if (key === "searchAgainLabel" || key === "searchCommandLabel") {
                initialValue = initialValue[lang] || "";
            }
            self[key] = ko.observable(initialValue);
        });
        self.searchWorkflow = ko.observable(self.getWorkflow(searchConfig.autoLaunch, searchConfig.defaultSearch));
        self.searchProperties = ko.observableArray();
        self.defaultProperties = ko.observableArray();

        // Parse searchRelevant into DEFAULT_CLAIM_RELEVANT, which controls a checkbox,
        // and the remainder of the expression, if any, which appears in a textbox.
        // Note that this fragile parsing logic needs to match the self.relevant calculation below
        // and cannot be changed without migrating existing CaseSearch documents
        var defaultRelevant = false,
            prefix = "(" + DEFAULT_CLAIM_RELEVANT + ") and (",
            extraRelevant = "",
            searchRelevant = searchConfig.searchRelevant || "";
        if (searchRelevant) {
            searchRelevant = searchRelevant.trim();
            if (searchRelevant === DEFAULT_CLAIM_RELEVANT) {
                defaultRelevant = true;
                extraRelevant = "";
            } else if (searchRelevant.startsWith(prefix)) {
                defaultRelevant = true;
                extraRelevant = searchRelevant.substr(prefix.length, searchRelevant.length - prefix.length - 1);
            } else {
                extraRelevant = searchRelevant;
            }
        }
        self.extraRelevant = ko.observable(extraRelevant);
        self.defaultRelevant = ko.observable(defaultRelevant);

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
        self.relevant = ko.computed(function () {
            if (self.defaultRelevant()) {
                if (self.extraRelevant().trim() === "") {
                    return DEFAULT_CLAIM_RELEVANT;
                } else {
                    // Note this needs to match the initialization logic for defaultRelevant and extraRelevant above
                    return "(" + DEFAULT_CLAIM_RELEVANT + ") and (" + self.extraRelevant().trim() + ")";
                }
            }
            return self.extraRelevant().trim();
        });

        self.serialize = function () {
            return _.extend({
                properties: self._getProperties(),
                session_var: self.sessionVar(),
                relevant: self.relevant(),
                search_button_display_condition: self.searchButtonDisplayCondition(),
                search_command_label: self.searchCommandLabel(),
                search_again_label: self.searchAgainLabel(),
                search_filter: self.searchFilter(),
                include_closed: self.includeClosed(),
                default_properties: self._getDefaultProperties(),
                blacklisted_owner_ids_expression: self.blacklistedOwnerIdsExpression(),
            }, self.serializeWorkflow());
        };

        _.each(searchConfigObservableKeys, function (key) {
            self[key].subscribe(function () {
                saveButton.fire('change');
            });
        });
        self.searchWorkflow.subscribe(function () {
            saveButton.fire('change');
        });
        self.relevant.subscribe(function () {
            saveButton.fire('change');
        });
        self.searchProperties.subscribe(function () {
            saveButton.fire('change');
        });
        self.defaultProperties.subscribe(function () {
            saveButton.fire('change');
        });

        return self;
    };

    return {
        searchConfigKeys: searchConfigKeys,
        searchViewModel: searchViewModel,
    };
});
