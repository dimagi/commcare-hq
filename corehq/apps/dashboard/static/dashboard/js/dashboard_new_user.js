/* globals hqDefine */
hqDefine("static/dashboard/js/dashboard_new_user", function() {
    $(function() {
        hqImport('analytics/js/kissmetrics').track.event('Visited new user dashboard');
        var $links = [];
        var templates = hqImport('hqwebapp/js/initial_page_data').get('templates');
        _.each(templates, function(template, index) {
            $links.push($('.dashboard-link[data-index="' + index + '"]'));
            hqImport('analytics/js/google').track.click($links[index], 'Dashboard', 'Welcome Tile', template.action);
            hqImport('analytics/js/kissmetrics').track.internalClick($links[index], template.description);
            hqImport('analytics/js/kissmetrics').track.internalClick($links[index], 'Clicked App Template Tile');
        });
    });
});
