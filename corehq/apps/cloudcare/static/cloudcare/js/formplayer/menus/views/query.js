/*global DOMPurify, Marionette */

hqDefine("cloudcare/js/formplayer/menus/views/query", function () {
    var FormplayerFrontend = hqImport("cloudcare/js/formplayer/app");

    var QueryView = Marionette.View.extend({
        tagName: "tr",
        className: "formplayer-request",
        template: _.template($("#query-view-item-template").html() || ""),

        templateContext: function () {
            var imageUri = this.options.model.get('imageUri');
            var audioUri = this.options.model.get('audioUri');
            var appId = this.model.collection.appId;
            return {
                imageUrl: imageUri ? FormplayerFrontend.getChannel().request('resourceMap', imageUri, appId) : "",
                audioUrl: audioUri ? FormplayerFrontend.getChannel().request('resourceMap', audioUri, appId) : "",
            };
        },

        ui: {
            valueDropdown: 'select.query-field',
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
            submitButton: '#query-submit-button',
            valueDropdown: 'select.query-field',
        },

        events: {
            'change @ui.valueDropdown': 'changeDropdown',
            'click @ui.submitButton': 'submitAction',
        },

        getAnswers: function () {
            var $fields = $(".query-field"),
                answers = {},
                model = this.parentModel;
            $fields.each(function (index) {
                if (this.value !== '') {
                    answers[model[index].get('id')] = this.value;
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
            urlObject.setQuery(this.getAnswers());
            urlObject.setDoQuery(false);
            var fetchingPrompts = FormplayerFrontend.getChannel().request("app:select:menus", urlObject);
            $.when(fetchingPrompts).done(function (response) {
                for (var i = 0; i < response.models.length; i++) {
                    var choices = response.models[i].get('itemsetChoices');
                    if (choices) {
                        var $field = $($fields.get(i)),
                            value = parseInt($field.val()) || undefined;
                        self.collection.models[i].set({
                            itemsetChoices: choices,
                            value: value,
                        });
                        $field.trigger('change.select2');
                    }
                }
            });
        },

        submitAction: function (e) {
            e.preventDefault();
            FormplayerFrontend.trigger("menu:query", this.getAnswers());
        },
    });

    return function (data) {
        return new QueryListView(data);
    };
});
