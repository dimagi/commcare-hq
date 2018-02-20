hqDefine("app_manager/js/details/case_claim", function() {
    var searchViewModel = function (searchProperties, includeClosed, defaultProperties, lang,
        searchButtonDisplayCondition, blacklistedOwnerIdsExpression, saveButton) {
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
    };

    var createSearchViewModel = function (searchProperties, includeClosed, defaultProperties, lang,
        searchButtonDisplayCondition, blacklistedOwnerIdsExpression,
        saveButton) {
        return new searchViewModel(searchProperties, includeClosed, defaultProperties, lang,
            searchButtonDisplayCondition, blacklistedOwnerIdsExpression, saveButton);
    };

    return {
        searchViewModel: createSearchViewModel,
    };
});
