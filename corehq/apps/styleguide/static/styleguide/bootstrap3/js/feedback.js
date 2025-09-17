import $ from 'jquery';
import 'hqwebapp/js/components/bootstrap3/feedback';

$(function () {
    var feedbackExample = function () {
        var self = {};

        self.featureName = 'My New Feature';

        // This should be a real url, either hard-coded in the django template or registered with the
        // registerurl template tag and then fetched here using initial_page_data.js's reverse.
        //
        // If url is left blank, it will use the submit_feedback view which requires
        // a login and domain and sends feedback to settings.FEEDBACK_EMAIL
        self.url = '';

        return self;
    };

    if ($("#feedback-example").length) {
        $("#feedback-example").koApplyBindings(feedbackExample());
    }
});
