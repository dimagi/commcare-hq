hqDefine("app_manager/js/details/case_claim", function () {
    var searchViewModel = function (searchProperties, includeClosed, defaultProperties, lang,
        searchButtonDisplayCondition, blacklistedOwnerIdsExpression, saveButton) {
        var self = {},
            DEFAULT_CLAIM_RELEVANT = "count(instance('casedb')/casedb/case[@case_id=instance('commcaresession')/session/data/case_id]) = 0";

        var searchProperty = function (name, label, appearance) {
            var self = {};
            self.name = ko.observable(name);
            self.label = ko.observable(label);
            self.appearance = ko.observable(appearance);

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

        var defaultProperty = function (property, defaultValue) {
            var self = {};
            self.property = ko.observable(property);
            self.defaultValue = ko.observable(defaultValue);

            self.property.subscribe(function () {
                saveButton.fire('change');
            });
            self.defaultValue.subscribe(function () {
                saveButton.fire('change');
            });

            return self;
        };

        self.searchButtonDisplayCondition = ko.observable(searchButtonDisplayCondition);
        self.relevant = ko.observable();
        self.default_relevant = ko.observable(true);
        self.includeClosed = ko.observable(includeClosed);
        self.searchProperties = ko.observableArray();
        self.defaultProperties = ko.observableArray();
        self.blacklistedOwnerIdsExpression = ko.observable(blacklistedOwnerIdsExpression);

        if (searchProperties.length > 0) {
            for (var i = 0; i < searchProperties.length; i++) {
                // property labels come in keyed by lang.
                var label = searchProperties[i].label[lang];
                self.searchProperties.push(searchProperty(
                    searchProperties[i].name,
                    label,
                    searchProperties[i].appearance
                ));
            }
        } else {
            self.searchProperties.push(searchProperty('', '', ''));
        }

        self.addProperty = function () {
            self.searchProperties.push(searchProperty('', ''));
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
                    };
                }
            );
        };

        if (defaultProperties.length > 0) {
            for (var k = 0; k < defaultProperties.length; k++) {
                self.defaultProperties.push(defaultProperty(
                    defaultProperties[k].property,
                    defaultProperties[k].defaultValue
                ));
            }
        } else {
            self.defaultProperties.push(defaultProperty('', ''));
        }
        self.addDefaultProperty = function () {
            self.defaultProperties.push(defaultProperty('',''));
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
        self._getRelevant = function () {
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
                search_button_display_condition: self.searchButtonDisplayCondition(),
                include_closed: self.includeClosed(),
                default_properties: self._getDefaultProperties(),
                blacklisted_owner_ids_expression: self.blacklistedOwnerIdsExpression(),
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
        self.searchButtonDisplayCondition.subscribe(function () {
            saveButton.fire('change');
        });
        self.blacklistedOwnerIdsExpression.subscribe(function () {
            saveButton.fire('change');
        });

        return self;
    };

    return {
        searchViewModel: searchViewModel,
    };
});
