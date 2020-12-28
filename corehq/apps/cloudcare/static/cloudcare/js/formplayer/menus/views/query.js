/*global Marionette */

hqDefine("cloudcare/js/formplayer/menus/views/query", function () {
    var FormplayerFrontend = hqImport("cloudcare/js/formplayer/app");

    var QueryView = Marionette.View.extend({
        tagName: "tr",
        className: "formplayer-request",
        template: _.template($("#query-view-item-template").html() || ""),

        templateContext: function () {
            var imageUri = this.options.model.get('imageUri'),
                audioUri = this.options.model.get('audioUri'),
                appId = this.model.collection.appId,
                queryDict = hqImport("cloudcare/js/formplayer/utils/util").getSavedQuery();
            return {
                imageUrl: imageUri ? FormplayerFrontend.getChannel().request('resourceMap', imageUri, appId) : "",
                audioUrl: audioUri ? FormplayerFrontend.getChannel().request('resourceMap', audioUri, appId) : "",
                initialValue: queryDict[this.options.model.get('id')] || '',
            };
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
        },

        events: {
            'click @ui.clearButton': 'clearAction',
            'click @ui.submitButton': 'submitAction',
        },

        clearAction: function () {
            var fields = $(".query-field");
            fields.each(function () {
                this.value = '';
            });
            hqImport("cloudcare/js/formplayer/utils/util").saveQuery({});
        },

        submitAction: function (e) {
            e.preventDefault();
            var payload = {};
            var fields = $(".query-field");
            var model = this.parentModel;
            fields.each(function (index) {
                if (this.value !== '') {
                    payload[model[index].get('id')] = this.value;
                }
            });
            FormplayerFrontend.trigger("menu:query", payload);
        },
    });

    return function (data) {
        return new QueryListView(data);
    };
});
