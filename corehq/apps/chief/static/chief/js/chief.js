(function() {
    "strict"

    window.Chief = {
        ViewModels: {},
    };

    Chief.ViewModels.InitiateDeploy = function() {
        var self = this;
        self.env = ko.observable(null);
        self.env.subscribe(function(newEnv) {
            $.post('/hq/chief/prepare/', { env: newEnv }).done(function(response) {
                console.log(response);
                return $.get('/hq/chief/submodules/', { env: newEnv }).done(function(response) {
                    console.log(response);
                    self.submodules(response.submodules);
                });
            })
        });
        self.submodules = ko.observableArray([]);
        self.submoduleToCommit = ko.observableArray([]);
        self.initiateDeploy = function() {
            $('#deploy-form').submit();
        };
    };

    Chief.ViewModels.PreviousReleases = function() {
        var self = this;
        self.init();
        self.environments = ko.observableArray([]);
        self.releases = ko.observableArray([]);

    };
    Chief.ViewModels.PreviousReleases.prototype.init = function() {
        var self = this;
        $.get('/hq/chief/releases').done(function(response) {
            console.log(response);
            self.environments(_.keys(response));
            _.each(response, function(releases, env) {
                response[env] = _.map(releases, self.parseRelease);
            })
            self.releases(response);
        });
    };
    Chief.ViewModels.PreviousReleases.prototype.parseRelease = function(release) {
        var dateParts = _.last(release.split('/')).split('_');
        // Convert the raw date format we use to ISO string
        var date = new Date(dateParts[0] + 'T' + dateParts[1].replace('.', ':') + ':00');
        console.log(date);
        return {
            path: release,
            date: date
        }

    };


    ko.applyBindings(new Chief.ViewModels.InitiateDeploy(), $('#deploy-modal')[0]);
    ko.applyBindings(new Chief.ViewModels.PreviousReleases(), $('#previous-releases')[0]);

})();
