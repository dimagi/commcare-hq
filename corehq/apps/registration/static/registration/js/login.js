hqDefine('registration/js/login', [
    'jquery',
    'blazy/blazy',
    'nic_compliance/js/encoder',
], function(
    $,
    Blazy
) {
    $(function () {
        // Blazy for loading images asynchronously
        // Usage: specify the b-lazy class on an element and adding the path
        // to the image in data-src="{% static 'path/to/image.jpg' %}"
        new Blazy({
            container: 'body',
        });
    });
});
