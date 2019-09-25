hqDefine("hqmedia/js/references_main", function () {
    function MultimediaReferenceController() {
        var self = {};
        self.references = ko.observableArray();
        self.showMissingReferences = ko.observable(false);
        self.totals = ko.observableArray();

        self.isInitialLoad = ko.observable(true);
        self.showPaginationSpinner = ko.observable(false);
        self.itemsPerPage = ko.observable();
        self.totalItems = ko.observable();

        self.toggleRefsText = ko.computed(function () {
            return (self.showMissingReferences()) ? gettext("Show All References") : gettext("Show Only Missing References");
        }, self);

        self.goToPage = function (page) {
            self.showPaginationSpinner(true);
            var includeTotal = page === 1;
            $.ajax({
                url: hqImport("hqwebapp/js/initial_page_data").reverse('hqmedia_references'),
                data: {
                    json: 1,
                    page: page,
                    limit: self.itemsPerPage(),
                    only_missing: self.showMissingReferences(),
                    include_total: includeTotal,
                },
                success: function (data) {
                    self.isInitialLoad(false);
                    self.showPaginationSpinner(false);
                    self.references(_.compact(_.map(data.references, function (ref) {
                        var objRef = data.object_map[ref.path];
                        if (ref.media_class === "CommCareImage") {
                            var imageRef = hqImport('hqmedia/js/media_reference_models').ImageReference(ref);
                            imageRef.setObjReference(objRef);
                            return imageRef;
                        } else if (ref.media_class === "CommCareAudio") {
                            var audioRef = hqImport('hqmedia/js/media_reference_models').AudioReference(ref);
                            audioRef.setObjReference(objRef);
                            return audioRef;
                        } else if (ref.media_class === "CommCareVideo") {
                            var videoRef = hqImport('hqmedia/js/media_reference_models').VideoReference(ref);
                            videoRef.setObjReference(objRef);
                            return videoRef;
                        }
                        // Other multimedia, like HTML print templates, is ignored by the reference checker
                        // It should already have been filtered out server-side.
                        throw new Error("Found unexpected media class: " + ref.media_class);
                    })));
                    if (includeTotal) {
                        self.totalItems(data.total_rows);
                        self.totals(data.totals);
                    }
                    $('.preview-media').tooltip();
                },
                error: function () {
                    self.showPaginationSpinner(false);
                    hqImport('hqwebapp/js/alert_user').alert_user(gettext("Error fetching multimedia, " +
                        "please try again or report an issue if the problem persists."), 'danger');
                },
            });
        };

        self.toggleMissingRefs = function () {
            self.showMissingReferences(!self.showMissingReferences());
            self.goToPage(1);
        };

        self.incrementTotals = function (trigger, event, data) {
            var newTotals = _.map(self.totals(), function (media) {
                if (media.media_type === data.media_type && media.paths.indexOf(data.path) < 0) {
                    media = _.clone(media);
                    media.paths.push(data.path);
                    media.matched = media.paths.length;
                }
                return media;
            });
            self.totals(newTotals);
        };

        self.goToPage(1);

        return self;
    }

    $(function () {
        $("#multimedia-reference-checker").koApplyBindings(MultimediaReferenceController());
    });
});
