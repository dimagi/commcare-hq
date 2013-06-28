// list of default repos to load build status for
var build_repos = ['commcare-hq','dimagi-utils','couchexport','couchlog','couchforms',
        'commcare-export','fluff','casexml','ctable','sql-agg','receiver','pillowtop'];

// list of repos to load PR's for (in addition to all repos which are submodules of commcare-hq)
var pullRepos = ['commcare-hq', 'sql-agg'];

var Dashboard = function () {
    var self = this;

    self.vm = null;
    self.page = ko.observable();
    self.build = ko.observable(new BuildStatus(self));
    self.pulls = ko.observable(new Pulls(self));

    self.total = ko.observable(0);
    self.current = ko.observable(0);
    self.showProgress = ko.observable(false);

    self.progress = ko.computed(function() {
        if (self.total() == 0){
            return '0%';
        }
        return Math.round(self.current() * 100 / self.total()) + '%';
    });

    self.progressCompletionListener = null;

    self.startProgress = function(total) {
        self.showProgress(true);
        self.current(0);
        self.total(total);
    }

    self.incrementProgress = function() {
        self.current(self.current() + 1);
        if (self.current() == self.total()) {
            self.total(0);
            self.current(0);
            self.showProgress(false);
            if (self.progressCompletionListener){
                self.progressCompletionListener();
                self.progressCompletionListener = null;
            }
        }
    }

    self.loadBuildStatus = function() {
        self.page('build');
        self.build().reloadDefault();
    }

    self.loadPulls = function() {
        self.page('pulls');
        self.pulls().reload();
//        self.pulls().sort(-1);
    }

    self.bind = function() {
        $(function(){
            ko.applyBindings(self);
        });
    }

    self.foreachRepo = function (callback) {
        function getRepos(url) {
            $.ajax({
                type: 'GET',
                dataType: 'jsonp',
                url: url,
                success: function(response){
                    self.total(dash.total() + response.data.length);

                    $.each(response.data, function(i, repo) {
                        callback(repo);
                    });

                    $.each(response.meta.Link, function(i, link){
                        var url = link[0];
                        var type = link[1].rel;
                        if (type == 'next') {
                            getRepos(url);
                        }
                    })
                }
            });
        }
        getRepos('https://api.github.com/orgs/dimagi/repos?type=public');
    }
}

var Pulls = function(dash) {
    var self = this;

    self.pulls = ko.observableArray();
    self.fails = ko.observableArray();
    self.sortDir = ko.observable('asc');
    self.sortBy = ko.observable('updated');

    self.sortAsc = function(by) {
        self.sortBy(by);
        self.sortDir('asc');
        self.sort();
    }

    self.sortDesc = function(by) {
        self.sortBy(by);
        self.sortDir('desc');
        self.sort();
    }

    self.reload = function() {
        dash.startProgress(pullRepos.length);
        dash.progressCompletionListener = self.sort;
        self.pulls.removeAll();
        self.fails.removeAll();
        $.each(pullRepos, function(i, name){
            self.loadPulls({name: name});
        });
//        dash.foreachRepo(self.loadPulls);
        $.get('https://api.github.com/repos/dimagi/commcare-hq/contents/submodules', function(subs) {
            dash.total(dash.total() + subs.length);
            $.each(subs, function(i, sub) {
                var reponame = sub.git_url.replace('https://api.github.com/repos/dimagi/', '').split('/', 1)[0];
                self.loadPulls({name: reponame});
            });
        });
    }

    self.loadPulls = function(repo) {
        var reponame = repo.name;
        $.get('https://api.github.com/repos/dimagi/'+ reponame +'/pulls', function(pulls) {
            $.each(pulls, function(i, pull){
                self.pulls.push({
                    repo: reponame,
                    url: pull.html_url,
                    number: pull.number,
                    title: pull.title,
                    created: pull.created_at,
                    updated: pull.updated_at,
                    hoursSinceUpdate: Math.round(Math.abs(new Date() - Date.parse(pull.updated_at)) / ( 60*60) / 1000),
                    user: {
                        name: pull.user.login,
                        url: pull.user.url,
                        avatar_url: pull.user.avatar_url
                    }
                });
            });
        }).fail(function(){
            self.fails.push({
                name: repo.name
            });
        }).always(function(){
            dash.incrementProgress();
        });
    }

    self.sort = function() {
        var dir = self.sortDir() == 'asc' ? 1 : -1;
        self.pulls.sort(function(left, right) {
            if (self.sortBy() == 'updated') {
                return (left.hoursSinceUpdate - right.hoursSinceUpdate) * dir;
            } else if (self.sortBy() == 'repo') {
                var lr = left.repo.toLowerCase(),
                    rr = right.repo.toLowerCase();
                return lr == rr ? 0 : (lr < rr ? -1 : 1) * dir
            } else if (self.sortBy() == 'user') {
                var lu = left.user.name.toLowerCase(),
                    ru = right.user.name.toLowerCase();
                return lu == ru ? 0 : (lu < ru ? -1 : 1) * dir
            }
        });
    }
}

var BuildStatus = function(dash) {
    var self = this;

    self.reposSuccess = ko.observableArray();
    self.reposFail = ko.observableArray();
    self.reposNoBuild = ko.observableArray();
    self.reposError = ko.observableArray();

    self.reloadAll = function() {
        self.reset();
        dash.startProgress(0);
        dash.foreachRepo(self.getBuildStatus);
    }

    self.reloadDefault = function() {
        self.reset();
        dash.startProgress(build_repos.length);
        $.each(build_repos, function(i, reponame) {
             self.getBuildStatus({name: reponame});
        });
    }

    self.reloadFailing = function() {
        var failing = self.reposFail.removeAll();
        dash.startProgress(failing.length);
        $.each(failing, function(i, repo) {
             self.getBuildStatus(repo);
        });
    }

    self.getBuildStatus = function(repo) {
        var name = repo.name;
        $.get('https://api.travis-ci.org/repos/dimagi/' + name + '/builds.json', function(tData){
            if (tData.length == 0) {
                self.reposNoBuild.push({
                   name: name,
                   status: 'no_build'
                });
            } else {
                var latest_master_build = $.grep(tData, function(build){
                   return build.branch === 'master';
                })[0];
                if (latest_master_build.state === 'finished' && latest_master_build.result === 0) {
                    self.reposSuccess.push({
                       name: name,
                       status: 'build'
                    });
                } else {
                    self.reposFail.push({
                       name: name,
                       status: 'build'
                    });
                }
            }
        }).fail(function(){
            self.reposError.push({
               name: name,
               status: 'error'
            });
        }).always(function() {
            dash.incrementProgress();
        });
    }

    self.reset = function() {
        self.reposSuccess.removeAll();
        self.reposFail.removeAll();
        self.reposNoBuild.removeAll();
        self.reposError.removeAll();
    }
}