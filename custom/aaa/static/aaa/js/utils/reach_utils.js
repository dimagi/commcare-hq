hqDefine("aaa/js/utils/reach_utils", [
    'moment/moment',
    'hqwebapp/js/initial_page_data',
], function (
    moment,
    initialPageData
) {
    var reachUtils = function () {
        var self = {};

        self.toIndiaFormat = function (number) {
            if (!number) {
                return '0';
            }
            number = Number(number).toFixed(0).toString();
            var numbers  = number.split('.');
            var lastThree = '';
            var otherNumbers = '';
            if (numbers.length === 2) {
                lastThree = numbers[0].substring(numbers[0].length - 3);
                otherNumbers = numbers[0].substring(0, numbers[0].length - 3);
                if (otherNumbers !== '')
                    lastThree = ',' + lastThree;

                return otherNumbers.replace(/\B(?=(\d{2})+(?!\d))/g, ",") + lastThree + "." + numbers[1];
            }
            else {
                lastThree = number.substring(number.length - 3);
                otherNumbers = number.substring(0, number.length - 3);
                if (otherNumbers !== '')
                    lastThree = ',' + lastThree;

                return otherNumbers.replace(/\B(?=(\d{2})+(?!\d))/g, ",") + lastThree;
            }
        };

        self.monthName = function (month) {
            return moment.months()[month - 1];
        };

        self.toTitleCase = function (string) {
            if (string !== null && string !== void(0) && string.length > 0) {
                return _.map(string.split('_'), function (word) {
                    return word[0].toUpperCase() + word.substr(1).toLowerCase();
                }).join(' ')
            }
            return string;
        };

        return self;
    };

    var postData = function (options) {
        var self  = {};
        var userLocationId = initialPageData.get('user_location_id');
        self.selectedYear = ko.observable(options.selectedYear || moment().year());
        self.selectedMonth = ko.observable(options.selectedMonth || moment().month() + 1);
        self.selectedLocation = options.selectedLocation || userLocationId;
        self.selectedMinistry = options.selectedMinistry || initialPageData.get('user_role_type') || USERROLETYPES.MOHFW;
        self.selectedBeneficiaryType = ko.observable(options.selectedBeneficiaryType || null);
        return self;
    };

    var localStorage = function () {
        var self = {};
        self.locationHierarchy = ko.observableArray([]);
        self.showModal = ko.observable(false);
        return self;
    };

    var USERROLETYPES = {
        MOHFW: 'MoHFW',
        MWCD: 'MWCD',
    };

    var DEFAULTLOCATION = {
        id: 'all',
        name: 'All',
    };

    return {
        reachUtils: reachUtils,
        postData: postData,
        localStorage: localStorage,
        USERROLETYPES: USERROLETYPES,
        DEFAULTLOCATION: DEFAULTLOCATION,
    };
});
