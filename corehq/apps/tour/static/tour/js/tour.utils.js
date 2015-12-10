(function(window) {
    'use strict';

    window.TourUtils = {
        getEndTourAsync: function (endUrl) {
            return function (tour) {
                $.post(endUrl);
            };
        },
        getCustomTemplate: function () {
            return '<div class="popover guided-tour" role="tooltip"> <div class="arrow"></div> <h3 class="popover-title"></h3> <div class="popover-content"></div> <div class="popover-navigation"> <div class="btn-group"> <button class="btn btn-sm btn-default" data-role="prev">&laquo; Prev</button> <button class="btn btn-sm btn-default" data-role="next">Next &raquo;</button> <button class="btn btn-sm btn-default" data-role="pause-resume" data-pause-text="Pause" data-resume-text="Resume">Pause</button> </div> <button class="btn btn-sm btn-default" data-role="end">End tour</button> </div> </div>';
        }
    };

})(window);
