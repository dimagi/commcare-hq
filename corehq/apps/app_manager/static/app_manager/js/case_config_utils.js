hqDefine('app_manager/js/case_config_utils', function () {
    return {
        getQuestions: function (questions, filter, excludeHidden, includeRepeat, excludeTrigger) {
            // filter can be "all", or any of "select1", "select", or "input" separated by spaces
            var i, options = [],
                q;
            excludeHidden = excludeHidden || false;
            excludeTrigger = excludeTrigger || false;
            includeRepeat = includeRepeat || false;
            filter = filter.split(" ");
            if (!excludeHidden) {
                filter.push('hidden');
            }
            if (!excludeTrigger) {
                filter.push('trigger');
            }
            var allowAttachments = hqImport('hqwebapp/js/toggles').toggleEnabled('MM_CASE_PROPERTIES');
            for (i = 0; i < questions.length; i += 1) {
                q = questions[i];
                if (filter[0] === "all" || filter.indexOf(q.tag) !== -1) {
                    if (includeRepeat || !q.repeat) {
                        if (!excludeTrigger || q.tag !== "trigger") {
                            if (allowAttachments || q.tag !== "upload") {
                                options.push(q);
                            }
                        }
                    }
                }
            }
            return options;
        },
        getAnswers: function (questions, condition) {
            var i, q, o, value = condition.question,
                found = false,
                options = [];
            for (i = 0; i < questions.length; i += 1) {
                q = questions[i];
                if (q.value === value) {
                    found = true;
                    break;
                }
            }
            if (found && q.options) {
                for (i = 0; i < q.options.length; i += 1) {
                    o = q.options[i];
                    options.push(o);
                }
            }
            return options;
        },
        // This function depends on initial page data, so it should be called within a document ready handler
        initRefreshQuestions: function (questionsObservable) {
            var initialPageData = hqImport("hqwebapp/js/initial_page_data"),
                formUniqueId = initialPageData.get("form_unique_id");
            if (formUniqueId) {
                var currentAppUrl = initialPageData.reverse("current_app_version"),
                    oldVersion = initialPageData.get("app_subset").version;
                $(document).on("ajaxComplete", function (e, xhr, options) {
                    if (options.url === currentAppUrl) {
                        var newVersion = xhr.responseJSON.currentVersion;
                        if (newVersion > oldVersion) {
                            oldVersion = newVersion;
                            $.get({
                                url: initialPageData.reverse('get_form_questions'),
                                data: {
                                    form_unique_id: formUniqueId,
                                },
                                success: function (data) {
                                    questionsObservable(data);
                                },
                            });
                        }
                    }
                });
            }
        },
        filteredSuggestedProperties: function (suggestedProperties, properties) {
            var used_properties = _.map(properties, function (x) {
                return x.key();
            });
            return _(suggestedProperties).difference(used_properties);
        },
        propertyDictToArray: function (required, property_dict, caseConfig, keyIsPath) {
            var property_array = _(property_dict).map(function (value, key) {
                return {
                    path: !keyIsPath ? value : key,
                    key: !keyIsPath ? key : value,
                    required: false,
                };
            });
            property_array = _(property_array).sortBy(function (property) {
                return caseConfig.questionScores[property.path] * 2 + (property.required ? 0 : 1);
            });
            return required.concat(property_array);
        },
        propertyArrayToDict: function (required, property_array) {
            var property_dict = {},
                extra_dict = {};
            _(property_array).each(function (case_property) {
                var key = case_property.key;
                var path = case_property.path;
                if (key || path) {
                    if (_(required).contains(key) && case_property.required) {
                        extra_dict[key] = path;
                    } else {
                        property_dict[key] = path;
                    }
                }
            });
            return [property_dict, extra_dict];
        },
        preloadArrayToDict: function (preloadArray) {
            // i.e. {i.path: i.key for i in preloadArray if i.key or i.path}
            return _.object(
                _.map(
                    _.filter(preloadArray, function (i) { return (i.key || i.path); }),
                    function (i) { return [i.path, i.key]; }
                )
            );
        },
    };
});
