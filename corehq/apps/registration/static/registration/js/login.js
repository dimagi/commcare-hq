hqDefine('registration/js/login', [
    'jquery',
    'blazy/blazy',
    'analytix/js/kissmetrix',
    'hqwebapp/js/captcha', // shows captcha
], function (
    $,
    blazy,
    kissmetrics
) {
    $(function () {
        // Blazy for loading images asynchronously
        // Usage: specify the b-lazy class on an element and adding the path
        // to the image in data-src="{% static 'path/to/image.jpg' %}"
        new blazy({
            container: 'body',
        });

        // populate username field if set in the query string
        const urlParams = new URLSearchParams(window.location.search);
        const username = urlParams.get('username');
        if (username) {
            var usernameElt = document.getElementById('id_auth-username');
            if (usernameElt) {
                usernameElt.value = username;
            }
        }

        kissmetrics.whenReadyAlways(function () {

            $('#cta-form-get-demo-button-body').click(function () {
                kissmetrics.track.event("Demo Workflow - Body Button Clicked");
            });

            $('#cta-form-get-demo-button-header').click(function () {
                kissmetrics.track.event("Demo Workflow - Header Button Clicked");
            });
        });
    });

});
