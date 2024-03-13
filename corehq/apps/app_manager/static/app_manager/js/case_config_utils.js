hqDefine('app_manager/js/case_config_utils', function () {
    return {
        getQuestions: function (questions, filter, excludeHidden, includeRepeat, excludeTrigger) {
            // filter can be "all", or any of "select1", "select", or "input" separated by spaces
            var i,
                options = [],
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
            var i,
                q,
                o,
                value = condition.question,
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
            var usedProperties = _.map(properties, function (x) {
                return x.key();
            });
            return _(suggestedProperties).difference(usedProperties);
        },
        propertyDictToArray: function (required, propertyDict, caseConfig) {
            var propertyArray = _(propertyDict).map(function (conditionalCaseUpdate, caseName) {
                return {
                    path: conditionalCaseUpdate.question_path,
                    key: caseName,
                    required: false,
                    save_only_if_edited: conditionalCaseUpdate.update_mode === 'edit',
                };
            });
            propertyArray = _(propertyArray).sortBy(function (property) {
                return caseConfig.questionScores[property.path] * 2 + (property.required ? 0 : 1);
            });
            return required.concat(propertyArray);
        },
        propertyArrayToDict: function (required, propertyArray) {
            var propertyDict = {},
                extraDict = {};
            _(propertyArray).each(function (caseProperty) {
                var key = caseProperty.key;
                var path = caseProperty.path;
                var updateMode = caseProperty.save_only_if_edited ? 'edit' : 'always';
                if (key || path) {
                    if (_(required).contains(key) && caseProperty.required) {
                        extraDict[key] = {question_path: path, update_mode: updateMode};
                    } else {
                        propertyDict[key] = {question_path: path, update_mode: updateMode};
                    }
                }
            });
            return [propertyDict, extraDict];
        },
        preloadDictToArray: function (propertyDict, caseConfig) {
            var propertyArray = _(propertyDict).map(function (path, caseName) {
                return {
                    path: caseName,
                    key: path,
                    required: false,
                    save_only_if_edited: false,
                };
            });
            propertyArray = _(propertyArray).sortBy(function (property) {
                return caseConfig.questionScores[property.path] * 2 + (property.required ? 0 : 1);
            });
            return propertyArray;
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
