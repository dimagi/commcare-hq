/*global FormplayerFrontend */

FormplayerFrontend.module("Utils.Views", function (Views, FormplayerFrontend, Backbone, Marionette) {

    Views.ProgressView = Marionette.ItemView.extend({
        template: "#progress-view-template",

        setProgress: function(progress, duration) {
            // Due to jQuery bug, can't use .animate() with % until jQuery 3.0
            $(this.el).find('.js-progress-bar').css('transition', duration + 'ms');
            $(this.el).find('.js-progress-bar').width(progress * 100 + '%');
        },
    });
});

