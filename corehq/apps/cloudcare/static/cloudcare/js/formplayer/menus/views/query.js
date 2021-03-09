/*global DOMPurify, Marionette*/

hqDefine("cloudcare/js/formplayer/menus/views/query", function () {
    // 'hqwebapp/js/hq.helpers' is a dependency. It needs to be added
    // explicitly when webapps is migrated to requirejs
    var FormplayerFrontend = hqImport("cloudcare/js/formplayer/app");
    var separator = " to ";
    var Const = hqImport("cloudcare/js/form_entry/const"),
        Utils = hqImport("cloudcare/js/form_entry/utils"),
        initialPageData = hqImport("hqwebapp/js/initial_page_data");

    var QueryView = Marionette.View.extend({
        tagName: "tr",
        className: "formplayer-request",
        template: _.template($("#query-view-item-template").html() || ""),

        templateContext: function () {
            var imageUri = this.options.model.get('imageUri'),
                audioUri = this.options.model.get('audioUri'),
                appId = this.model.collection.appId,
                value = this.options.model.get('value');

            // Initial values are sent from formplayer as strings, but dropdowns expect an integer
            if (value && this.options.model.get('input') === "select1") {
                value = parseInt(value);
            }

            return {
                imageUrl: imageUri ? FormplayerFrontend.getChannel().request('resourceMap', imageUri, appId) : "",
                audioUrl: audioUri ? FormplayerFrontend.getChannel().request('resourceMap', audioUri, appId) : "",
                value: value,
            };
        },

        initialize: function () {
            // If input doesn't have a default value, check to see if there's a sticky value from user's last search
            if (!this.options.model.get('value')) {
                this.options.model.set('value', hqImport("cloudcare/js/formplayer/utils/util").getStickyQueryInputs()[this.options.model.get('id')]);
            }
        },

        ui: {
            valueDropdown: 'select.query-field',
            hqHelp: '.hq-help',
            dateRange: 'input.daterange',
            queryField: '.query-field',
        },

        modelEvents: {
            'change': 'render',
        },

        geocoderItemCallback: function (addressTopic) {
            return function (item) {
                var broadcastObj = Utils.getBroadcastObject(item);
                $.publish(addressTopic, broadcastObj);
                return item.place_name;
            };
        },

        geocoderOnClearCallback: function (addressTopic) {
            return function () {
                $.publish(addressTopic, Const.NO_ANSWER);
            };
        },

        updateReceiver: function (element) {
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
                if (element.is('input')) {
                    element.val(value);
                }
                else {
                    // Set lookup table option by label
                    var option = element.find("option").filter(function (_) {
                        return $(this).text() === value;
                    });
                    if (option.length > 1) {
                        option.attr('selected', true);
                    }
                }
            };
        },

        onAttach: function () {
            var self = this;
            this.ui.queryField.each(function () {
                // Set geocoder receivers to subscribe
                var receiveExpression = $(this).data().receive;
                if (receiveExpression !== undefined && receiveExpression !== "") {
                    var topic = receiveExpression.split("-")[0];
                    $.subscribe(topic, self.updateReceiver($(this)));
                }
                // Set geocoder address publish
                var addressTopic = $(this).data().address;
                if (addressTopic !== undefined && addressTopic !== "") {
                    // set this up as mapbox input
                    var inputId = addressTopic + "_mapbox";
                    if (!initialPageData.get("has_geocoder_privs")) {
                        $("#" + inputId).addClass('unsupported alert alert-warning');
                        $("#" + inputId).text(gettext(
                            "Sorry, this input is not supported because your project doesn't have a Geocoder privilege")
                        );
                        return true;
                    }
                    Utils.renderMapboxInput(
                        inputId,
                        self.geocoderItemCallback(addressTopic),
                        self.geocoderOnClearCallback(addressTopic),
                        initialPageData
                    );
                    var divEl = $('.mapboxgl-ctrl-geocoder');
                    divEl.css("max-width", "none");
                    divEl.css("width", "100%");
                }
            });
        },

        onRender: function () {
            this.ui.valueDropdown.select2({
                allowClear: true,
                placeholder: " ",   // required for allowClear to work
                escapeMarkup: function (m) { return DOMPurify.sanitize(m); },
            });
            this.ui.hqHelp.hqHelp();
            this.ui.dateRange.daterangepicker({
                locale: {
                    format: 'YYYY-MM-DD',
                    separator: separator,
                    cancelLabel: 'Clear',
                },
                autoUpdateInput: false,
            });
            this.ui.dateRange.on('cancel.daterangepicker', function () {
                $(this).val('');
            });
            this.ui.dateRange.on('apply.daterangepicker', function(ev, picker) {
                $(this).val(picker.startDate.format('YYYY-MM-DD') + separator + picker.endDate.format('YYYY-MM-DD'));
            });
        },
    });

    var QueryListView = Marionette.CollectionView.extend({
        tagName: "div",
        template: _.template($("#query-view-list-template").html() || ""),
        childView: QueryView,
        childViewContainer: "tbody",

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
            valueDropdown: 'select.query-field',
            valueInput: 'input.query-field',
        },

        events: {
            'change @ui.valueDropdown': 'changeDropdown',
            'change @ui.valueInput': 'setStickyQueryInputs',
            'click @ui.clearButton': 'clearAction',
            'click @ui.submitButton': 'submitAction',
        },

        getAnswers: function () {
            var $fields = $(".query-field"),
                answers = {},
                model = this.parentModel;
            $fields.each(function (index) {
                var answer = null;
                if (this.value !== '') {
                    if (model[index].get('input') === 'daterange') {
                        // special format handled by CaseSearch API
                        answer = "__range__" + this.value.replace(separator, "__");
                    } else if (model[index].get('input') === 'address') {
                        // skip geocoder address
                        return true;
                    } else {
                        answer = this.value;
                    }
                    answers[model[index].get('id')] = answer;
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
            urlObject.setQueryData(this.getAnswers(), false);
            var fetchingPrompts = FormplayerFrontend.getChannel().request("app:select:menus", urlObject);
            $.when(fetchingPrompts).done(function (response) {
                for (var i = 0; i < response.models.length; i++) {
                    var choices = response.models[i].get('itemsetChoices');
                    if (choices) {
                        var $field = $($fields.get(i)),
                            value = parseInt(response.models[i].get('value'));
                        $field.select2('close');    // force close dropdown, the set below can interfere with this when clearing selection
                        self.collection.models[i].set({
                            itemsetChoices: choices,
                            value: value,
                        });
                        $field.trigger('change.select2');
                    }
                }
                self.setStickyQueryInputs();
            });
        },

        clearAction: function () {
            var self = this,
                fields = $(".query-field");
            fields.each(function () {
                this.value = '';
                $(this).trigger('change.select2');
            });
            self.setStickyQueryInputs();
            // clear geocoder input if any
            $('.mapboxgl-ctrl-geocoder--button').click()
        },

        submitAction: function (e) {
            e.preventDefault();
            FormplayerFrontend.trigger("menu:query", this.getAnswers());
        },

        setStickyQueryInputs: function () {
            var Util = hqImport("cloudcare/js/formplayer/utils/util");
            Util.setStickyQueryInputs(this.getAnswers());
        },
    });

    return function (data) {
        return new QueryListView(data);
    };
});
