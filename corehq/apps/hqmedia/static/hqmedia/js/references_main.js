hqDefine("hqmedia/js/references_main", [
    "jquery",
    "knockout",
    "underscore",
    "hqwebapp/js/bootstrap3/alert_user",
    "hqwebapp/js/initial_page_data",
    "hqmedia/js/media_reference_models",
    "app_manager/js/download_async_modal",    // for the 'Download ZIP' button
    "hqwebapp/js/components/pagination",
], function (
    $,
    ko,
    _,
    alertUser,
    initialPageData,
    mediaReferenceModels
) {
    function MultimediaReferenceController() {
        var self = {};
        self.references = ko.observableArray();
        self.totals = ko.observableArray();

        // Filtering
        self.query = ko.observable('');
        self.lang = ko.observable('all');
        self.lang.subscribe(function () {
            self.goToPage(1);
        });
        self.mediaClass = ko.observable('all');
        self.mediaClass.subscribe(function () {
            self.goToPage(1);
        });
        self.onlyMissing = ko.observable('false');
        self.onlyMissing.subscribe(function () {
            self.goToPage(1);
        });

        self.isInitialLoad = ko.observable(true);
        self.showPaginationSpinner = ko.observable(false);
        self.itemsPerPage = ko.observable();
        self.totalItems = ko.observable();

        self.goToPage = function (page) {
            self.showPaginationSpinner(true);
            var includeTotal = page === 1;
            $.ajax({
                url: initialPageData.reverse('hqmedia_references'),
                data: {
                    json: 1,
                    page: page,
                    limit: self.itemsPerPage(),
                    lang: self.lang() === "all" ? null : self.lang(),
                    media_class: self.mediaClass() === "all" ? "" : self.mediaClass(),
                    only_missing: self.onlyMissing(),
                    query: self.query(),
                    include_total: includeTotal,
                },
                success: function (data) {
                    self.isInitialLoad(false);
                    self.showPaginationSpinner(false);
                    self.references(_.map(data.references, function (ref) {
                        var objRef = data.object_map[ref.path];
                        if (ref.media_class === "CommCareImage") {
                            var imageRef = mediaReferenceModels.ImageReference(ref);
                            imageRef.setObjReference(objRef);
                            return imageRef;
                        } else if (ref.media_class === "CommCareAudio") {
                            var audioRef = mediaReferenceModels.AudioReference(ref);
                            audioRef.setObjReference(objRef);
                            return audioRef;
                        } else if (ref.media_class === "CommCareVideo") {
                            var videoRef = mediaReferenceModels.VideoReference(ref);
                            videoRef.setObjReference(objRef);
                            return videoRef;
                        }
                        // Other multimedia, like HTML print templates, is ignored by the reference checker
                        // It should already have been filtered out server-side.
                        throw new Error("Found unexpected media class: " + ref.media_class);
                    }));
                    if (includeTotal) {
                        self.totalItems(data.total_rows);
                        self.totals(data.totals);
                    }
                    $('.preview-media').tooltip();
                },
                error: function () {
                    self.showPaginationSpinner(false);
                    alertUser.alert_user(gettext("Error fetching multimedia, " +
                        "please try again or report an issue if the problem persists."), 'danger');
                },
            });
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
