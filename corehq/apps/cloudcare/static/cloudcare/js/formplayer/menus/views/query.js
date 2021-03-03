/*global DOMPurify, Marionette */

hqDefine("cloudcare/js/formplayer/menus/views/query", function () {
    // 'hqwebapp/js/hq.helpers' is a dependency. It needs to be added
    // explicitly when webapps is migrated to requirejs
    var FormplayerFrontend = hqImport("cloudcare/js/formplayer/app");
    var separator = " to ";

    // special format handled by CaseSearch API
    var encodeValue = function (model, value) {
            if (!value) {
                return value;
            }
            if (model.get("input") === "daterange") {
                return "__range__" + value.replace(separator, "__");
            }
            return value;
        }, decodeValue = function (model, value) {
            if (!value) {
                return value;
            }
            if (model.get("input") === "daterange") {
                return value.replace("__range__", "").replace("__", separator);
            }
            return value;
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
                var stickyValue = hqImport("cloudcare/js/formplayer/utils/util").getStickyQueryInputs()[this.options.model.get('id')];
                this.options.model.set('value', decodeValue(this.options.model, stickyValue));
            }
        },

        ui: {
            valueDropdown: 'select.query-field',
            hqHelp: '.hq-help',
            dateRange: 'input.daterange',
        },

        modelEvents: {
            'change': 'render',
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
                    cancelLabel: gettext('Clear'),
                },
                autoUpdateInput: false,
            });
            var self = this;
            this.ui.dateRange.on('cancel.daterangepicker', function () {
                $(this).val('').trigger('change');
            });
            this.ui.dateRange.on('apply.daterangepicker', function(ev, picker) {
                $(this).val(picker.startDate.format('YYYY-MM-DD') + separator + picker.endDate.format('YYYY-MM-DD')).trigger('change');
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
                if (this.value !== '') {
                    answers[model[index].get('id')] = encodeValue(model[index], this.value);
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
