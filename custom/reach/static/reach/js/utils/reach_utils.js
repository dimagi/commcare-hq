hqDefine("reach/js/utils/reach_utils", [
    'moment/moment'
], function(
    moment
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
                if(otherNumbers !== '')
                    lastThree = ',' + lastThree;

                return otherNumbers.replace(/\B(?=(\d{2})+(?!\d))/g, ",") + lastThree + "." + numbers[1];
            }
            else {
                lastThree = number.substring(number.length - 3);
                otherNumbers = number.substring(0, number.length - 3);
                if(otherNumbers !== '')
                    lastThree = ',' + lastThree;

                return otherNumbers.replace(/\B(?=(\d{2})+(?!\d))/g, ",") + lastThree;
            }
        };
        return self
    };

    var postData = function(options) {
        var self  = {};
        self.selectedYear = options.selectedYear || moment().year();
        self.selectedMonth = options.selectedMonth || moment().month() + 1;
        return self;
    };

    return {
        reachUtils: reachUtils,
        postData: postData,
    }
});
