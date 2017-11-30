/* globals hqDefine */
hqDefine("static/dashboard/js/dashboard_new_user", function() {
    $(function() {
        hqImport('analytix/js/kissmetrix').track.event('Visited new user dashboard');
        var $links = [];
        var templates = hqImport('hqwebapp/js/initial_page_data').get('templates');
        _.each(templates, function(template, index) {
            $links.push($('.dashboard-link[data-index="' + index + '"]'));
            hqImport('analytix/js/google').track.click($links[index], 'Dashboard', 'Welcome Tile', template.action);
            hqImport('analytix/js/kissmetrix').track.internalClick($links[index], template.description);
            hqImport('analytix/js/kissmetrix').track.internalClick($links[index], 'Clicked App Template Tile');
        });
    });
});
