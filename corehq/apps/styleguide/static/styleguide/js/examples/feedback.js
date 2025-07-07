import $ from 'jquery';
import initialPageData from 'hqwebapp/js/initial_page_data';
import 'hqwebapp/js/components/bootstrap5/feedback';

$(function () {
    $("#feedback-example").koApplyBindings(function () {
        let self = {};

        self.featureName = 'My New Feature';

        self.url = initialPageData.reverse("styleguide_submit_feedback_demo");

        return self;
    });
});
