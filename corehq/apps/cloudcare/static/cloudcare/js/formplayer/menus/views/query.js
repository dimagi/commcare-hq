/*global DOMPurify, Marionette, moment */


hqDefine("cloudcare/js/formplayer/menus/views/query", function () {
    // 'hqwebapp/js/hq.helpers' is a dependency. It needs to be added
    // explicitly when webapps is migrated to requirejs
    var kissmetrics = hqImport("analytix/js/kissmetrix");
    var FormplayerFrontend = hqImport("cloudcare/js/formplayer/app");
    var separator = " to ",
        dateFormat = "YYYY-MM-DD";
    var selectDelimiter = "#,#"; // Formplayer also uses this
    var Const = hqImport("cloudcare/js/form_entry/const"),
        Utils = hqImport("cloudcare/js/form_entry/utils"),
        initialPageData = hqImport("hqwebapp/js/initial_page_data");

    // special format handled by CaseSearch API
    var encodeValue = function (model, searchForBlank) {
            var value = model.get('value');
            if (value && model.get("input") === "daterange") {
                value = "__range__" + value.replace(separator, "__");
            } else if (value && model.get('input') === 'select') {
                value = value.join(selectDelimiter);
            }

            var queryProvided = _.isObject(value) ? !!value.length : !!value;
            if (searchForBlank && queryProvided) {
                return selectDelimiter + value;
            } else if (queryProvided) {
                return value;
            } else if (searchForBlank) {
                return "";
            }
        },
        decodeValue = function (model, value) {
            if (!_.isString(value)) {
                return [false, undefined];
            }
            var values = value.split(selectDelimiter),
                searchForBlank = _.contains(values, ""),
                values = _.without(values, "");

            if (model.get('input') === 'select') {
                value = values;
            } else if (values.length === 1) {
                value = values[0];
                if (model.get("input") === "daterange") {
                    value = value.replace("__range__", "").replace("__", separator);
                }
            } else {
                value = undefined;
            }
            return [searchForBlank, value];
        },
        geocoderItemCallback = function (addressTopic, model) {
            return function (item) {
                kissmetrics.track.event("Accessibility Tracking - Geocoder Interaction in Case Search");
                model.set('value', item.place_name);
                initMapboxWidget(model);
                var broadcastObj = Utils.getBroadcastObject(item);
                $.publish(addressTopic, broadcastObj);
                return item.place_name;
            };
        },
        geocoderOnClearCallback = function (addressTopic) {
            return function () {
                kissmetrics.track.event("Accessibility Tracking - Geocoder Interaction in Case Search");
                $.publish(addressTopic, Const.NO_ANSWER);
            };
        },
        updateReceiver = function (element) {
            return function (_event, broadcastObj) {
                // e.g. format is home-state, home-zipcode, home-us_state||country
                var receiveExpression = element.data().receive;
                var receiveField = receiveExpression.split("-")[1];
                var value = null;
                if (broadcastObj === undefined || broadcastObj === Const.NO_ANSWER) {
                    value = Const.NO_ANSWER;
                } else if (broadcastObj[receiveField]) {
                    value = broadcastObj[receiveField];
                } else {
                    // match home-us_state||country style
                    var fields = receiveField.split('||');
                    $.each(fields, function (i, field) {
                        if (broadcastObj[field] !== undefined) {
                            value = broadcastObj[field];
                            return false;
                        }
                    });
                }
                // lookup DOM element again, in case the element got rerendered
                var domElement = $('*[data-receive="' + receiveExpression + '"]');
                if (domElement.is('input')) {
                    domElement.val(value);
                    domElement.change();
                }
                else {
                    // Set lookup table option by label
                    var matchingOption = function (el) {
                        return el.find("option").filter(function (_) {
                            return $(this).text().trim() === value;
                        });
                    }
                    var option = matchingOption(domElement);
                    if (domElement[0].multiple === true) {
                        var val = option.val();
                        if (option.length === 1 && domElement.val().indexOf(val) === -1) {
                            domElement.val(
                                domElement.val().concat(val)
                            ).trigger("change");
                        }
                    }
                    else {
                        if (option.length === 1) {
                            domElement.val(String(option.index() - 1)).trigger("change");
                        } else {
                            domElement.val("-1").trigger('change');
                        }
                    }
                }
            };
        },
        initMapboxWidget = function (model) {
            var id = model.get('id'),
                inputId = id + "_mapbox",
                $field = $("#" + inputId);
            $(function () {
                kissmetrics.track.event("Accessibility Tracking - Geocoder Seen in Case Search");
            });
            if ($field.find('.mapboxgl-ctrl-geocoder--input').length === 0) {
                if (!initialPageData.get("has_geocoder_privs")) {
                    $("#" + inputId).addClass('unsupported alert alert-warning');
                    $("#" + inputId).text(gettext(
                        "Sorry, this input is not supported because your project doesn't have a Geocoder privilege")
                    );
                    return true;
                }
                Utils.renderMapboxInput(
                    inputId,
                    geocoderItemCallback(id, model),
                    geocoderOnClearCallback(id),
                    initialPageData
                );
                var divEl = $field.find('.mapboxgl-ctrl-geocoder');
                divEl.css("max-width", "none");
                divEl.css("width", "100%");
            }

            if (model.get('value')) {
                $field.find('.mapboxgl-ctrl-geocoder--input').val(model.get('value'));
            }
        };

    var QueryView = Marionette.View.extend({
        tagName: "tr",
        className: "formplayer-request",
        template: _.template($("#query-view-item-template").html() || ""),

        templateContext: function () {
            var imageUri = this.options.model.get('imageUri'),
                audioUri = this.options.model.get('audioUri'),
                appId = this.model.collection.appId,
                value = this.options.model.get('value');

            return {
                imageUrl: imageUri ? FormplayerFrontend.getChannel().request('resourceMap', imageUri, appId) : "",
                audioUrl: audioUri ? FormplayerFrontend.getChannel().request('resourceMap', audioUri, appId) : "",
                value: value,
                hasError: this.hasError,
                errorMessage: this.errorMessage,
            };
        },

        initialize: function () {
            this.parentView = this.options.parentView;
            this.model = this.options.model;
            this.hasError = false;
            this.errorMessage = null;

            var value = this.model.get('value'),
                allStickyValues = hqImport("cloudcare/js/formplayer/utils/util").getStickyQueryInputs(),
                stickyValue = allStickyValues[this.model.get('id')],
                [searchForBlank, stickyValue] = decodeValue(this.model, stickyValue);
            this.model.set('searchForBlank', searchForBlank);
            if (stickyValue && !value) {  // Sticky values don't override default values
                value = stickyValue;
            }
            if (this.model.get('input') === 'select' && _.isString(value)) {
                value = value.split(selectDelimiter);
            }
            this.model.set('value', value);
        },

        ui: {
            valueDropdown: 'select.query-field',
            hqHelp: '.hq-help',
            dateRange: 'input.daterange',
            date: 'input.date',
            queryField: '.query-field',
            searchForBlank: '.search-for-blank',
        },

        events: {
            'change @ui.queryField': 'changeQueryField',
            'dp.change @ui.queryField': 'changeDateQueryField',
            'click @ui.searchForBlank': 'toggleBlankSearch',
        },

        _isValid: function () {
            if (this.model.get("error")) {
                return false;
            }
            if (!this.model.get('required')) {
                return true;
            }
            var answer = this.getEncodedValue();
            return answer !== undefined && (answer === "" || answer.replace(/\s+/, "") !== "");
        },

        isValid: function () {
            var hasError = !this._isValid();
            if (hasError !== this.hasError) {
                if (hasError) {
                    this.errorMessage = this.model.get("error");
                } else {
                    this.model.set("error", null);
                    this.errorMessage = null;
                }
                this.hasError = hasError;
                this.render();
            }
            return !this.hasError;
        },

        clear: function () {
            var self = this;
            self.model.set('value', '');
            self.model.set('error', null);
            self.errorMessage = null;
            self.model.set('searchForBlank', false);
            if (self.ui.date.length) {
                self.ui.date.data("DateTimePicker").clear();
            }
            self.hasError = false;
            self.render();
            FormplayerFrontend.trigger('clearNotifications');
        },

        getEncodedValue: function () {
            if (this.model.get('input') === 'address') {
                return;  // skip geocoder address
            }
            var queryValue = $(this.ui.queryField).val(),
                searchForBlank = $(this.ui.searchForBlank).prop('checked');
            return encodeValue(this.model, searchForBlank);
        },

        changeQueryField: function (e) {
            if (this.model.get('input') === 'date') {
                // Skip because dates get handled by changeDateQueryField
                return;
            } else if (this.model.get('input') === 'select1' || this.model.get('input') === 'select') {
                this.model.set('value', $(e.currentTarget).val());
                this.parentView.changeDropdown(e);
            } else if (this.model.get('input') === 'address') {
                // geocoderItemCallback sets the value on the model
            } else {
                this.model.set('value', $(e.currentTarget).val());
            }
            this.parentView.setStickyQueryInputs();
        },
        changeDateQueryField: function (e) {
            this.model.set('value', $(e.currentTarget).val());
            this.parentView.setStickyQueryInputs();
        },

        toggleBlankSearch: function (e) {
            var self = this,
                searchForBlank = $(e.currentTarget).prop('checked');
            self.model.set('searchForBlank', searchForBlank);

            // When checking the blank search box for a geocoder field, toggle all its receiver fields
            if (self.model.get('input') === 'address') {
                _.each(self.model.collection.models, function (relatedModel) {
                    if (relatedModel.get('receive') && relatedModel.get('receive').split("-")[0] === self.model.get('id')) {
                        relatedModel.set('searchForBlank', searchForBlank);
                    }
                });
                initMapboxWidget(this.model);
            }
            self.parentView.setStickyQueryInputs();
        },

        onRender: function () {
            this.ui.valueDropdown.select2({
                allowClear: true,
                placeholder: " ",   // required for allowClear to work
                escapeMarkup: function (m) { return DOMPurify.sanitize(m); },
            });
            this.ui.hqHelp.hqHelp();
            this.ui.date.datetimepicker(_.extend(hqImport("cloudcare/js/util").dateTimePickerOptions(), {
                format: dateFormat,
            }));
            this.ui.dateRange.daterangepicker({
                locale: {
                    format: dateFormat,
                    separator: separator,
                },
                autoUpdateInput: false,
                "autoApply": true,
            });
            this.ui.dateRange.on('cancel.daterangepicker', function () {
                $(this).val('').trigger('change');
            });
            this.ui.dateRange.on('apply.daterangepicker', function(ev, picker) {
                $(this).val(picker.startDate.format(dateFormat) + separator + picker.endDate.format(dateFormat)).trigger('change');
            });
            this.ui.dateRange.on('change', function () {
                // Validate free-text input. Accept anything moment can recognize as a date, reformatting for ES.
                var $input = $(this),
                    oldValue = $input.val(),
                    parts = _.map(oldValue.split(separator), function (v) { return moment(v); }),
                    newValue = '';

                if (_.every(parts, function (part) { return part.isValid(); }))  {
                    if (parts.length === 1) { // condition where only one valid date is typed in rather than a range
                        newValue = oldValue + separator + oldValue;
                    } else if (parts.length === 2) {
                        newValue = parts[0].format(dateFormat) + separator + parts[1].format(dateFormat);
                    }
                }
                if (oldValue !== newValue) {
                    $input.val(newValue).trigger('change');
                }
            });
            if (this.model.get('hidden') === 'true') {
                this.$el.hide();
            }
        },

    });

    var QueryListView = Marionette.CollectionView.extend({
        tagName: "div",
        template: _.template($("#query-view-list-template").html() || ""),
        childView: QueryView,
        childViewContainer: "tbody",
        childViewOptions: function () { return {parentView: this}; },

        initialize: function (options) {
            this.parentModel = options.collection.models;
        },

        templateContext: function () {
            return {
                title: this.options.title,
            };
        },

        ui: {
            clearButton: '#query-clear-button',
            submitButton: '#query-submit-button',
            valueInput: 'input.query-field',
        },

        events: {
            'click @ui.clearButton': 'clearAction',
            'click @ui.submitButton': 'submitAction',
        },

        getAnswers: function () {
            var answers = {};
            this.children.each(function (childView) {
                var encodedValue = childView.getEncodedValue();
                if (encodedValue !== undefined) {
                    answers[childView.model.get('id')] = encodedValue;
                }
            });
            return answers;
        },

        changeDropdown: function (e) {
            e.preventDefault();
            var self = this;
            var $fields = $(".query-field");

            // If there aren't at least two dropdowns, there are no dependencies
            if ($fields.filter("select").length < 2) {
                return;
            }

            var Util = hqImport("cloudcare/js/formplayer/utils/util");
            var urlObject = Util.currentUrlToObject();
            urlObject.setQueryData(self.getAnswers(), false);
            var fetchingPrompts = FormplayerFrontend.getChannel().request("app:select:menus", urlObject);
            $.when(fetchingPrompts).done(function (response) {
                for (var i = 0; i < response.models.length; i++) {
                    var choices = response.models[i].get('itemsetChoices');
                    if (choices) {
                        var $field = $($fields.get(i)),
                            value = response.models[i].get('value');
                        if ($field.data('select2')) {
                            // force close dropdown, the set below can interfere with this when clearing selection
                            $field.select2('close');
                        }
                        if (value !== null) {
                            value = value.split(selectDelimiter);
                            value = _.filter(value, function (val) { return val !== ''; });
                            if (!$field.attr('multiple')) {
                                value = _.isEmpty(value) ? null : value[0];
                            }
                        }
                        self.collection.models[i].set({
                            itemsetChoices: choices,
                            value: value,
                        });
                        self.children.findByIndex(i).render();      // re-render with new choice values
                    }
                }
            });
        },

        clearAction: function () {
            var self = this;
            this.children.each(function (childView) {
                childView.clear();
                if (childView.model.get('input') === 'address') {
                    initMapboxWidget(childView.model);
                }
            });
            self.setStickyQueryInputs();
        },

        submitAction: function (e) {
            var self = this;
            e.preventDefault();

            var invalidFields = [];
            var errorHTML = gettext("Please check the following fields:");

            FormplayerFrontend.trigger('clearNotifications', errorHTML, true);

            var Util = hqImport("cloudcare/js/formplayer/utils/util");
            var urlObject = Util.currentUrlToObject();
            urlObject.setQueryData(self.getAnswers(), false);
            var fetchingPrompts = FormplayerFrontend.getChannel().request("app:select:menus", urlObject);

            $.when(fetchingPrompts).done(function (response) {
                for (var i = 0; i < response.models.length; i++) {
                    self.collection.models[i].set('error', response.models[i].get('error'));
                }
                self.children.each(function (childView) {
                    if (!childView.isValid()) {
                        invalidFields.push(childView.model.get('text'));
                    }
                });

                if (invalidFields.length) {
                    errorHTML += "<ul>" + _.map(invalidFields, function (f) {
                        return "<li>" + DOMPurify.sanitize(f) + "</li>";
                    }).join("") + "</ul>";
                    FormplayerFrontend.trigger('showError', errorHTML, true, false);

                    return;
                }

                FormplayerFrontend.trigger("menu:query", self.getAnswers());
            });

        },

        setStickyQueryInputs: function () {
            var Util = hqImport("cloudcare/js/formplayer/utils/util");
            Util.setStickyQueryInputs(this.getAnswers());
        },

        onAttach: function () {
            this.initGeocoders();
        },

        initGeocoders: function () {
            var self = this;
            _.each(self.collection.models, function (model, i) {
                var $field = $($(".query-field")[i]);

                // Set geocoder receivers to subscribe
                if (model.get('receive')) {
                    var topic = model.get('receive').split("-")[0];
                    $.subscribe(topic, updateReceiver($field));
                }

                // Set geocoder address publish
                if (model.get('input') === 'address') {
                    initMapboxWidget(model);
                }
            });
        },

    });

    return function (data) {
        return new QueryListView(data);
    };
});
