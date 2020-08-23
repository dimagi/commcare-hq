/*global _, Marionette */

hqDefine("cloudcare/js/formplayer/layout/views/progress_bar", function () {
    var ProgressView = Marionette.View.extend({
        template: _.template($("#progress-view-template").html() || ""),

        initialize: function (options) {
            this.progressMessage = options.progressMessage;
        },

        templateContext: function () {
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

    return function (options) {
        return new ProgressView(options);
    };
});

