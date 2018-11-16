/*global FormplayerFrontend */

FormplayerFrontend.module("Layout.Views", function (Views, FormplayerFrontend, Backbone, Marionette) {

    Views.ProgressView = Marionette.ItemView.extend({
        template: "#progress-view-template",

        initialize: function (options) {
            this.progressMessage = options.progressMessage;
        },

        templateHelpers: function () {
            return {
                progressMessage: this.progressMessage,
            };
        },

        setProgress: function (done, total, duration) {
            var progress = total === 0 ? 0 : done / total;
            // Due to jQuery bug, can't use .animate() with % until jQuery 3.0
            $(this.el).find('.js-progress-bar').css('transition', duration + 'ms');
            $(this.el).find('.js-progress-bar').width(progress * 100 + '%');
            if (total > 0) {
                $(this.el).find('.js-subtext small').text(
                    gettext('Completed: ') + done + '/' + total
                );
            }
        },
    });
});

