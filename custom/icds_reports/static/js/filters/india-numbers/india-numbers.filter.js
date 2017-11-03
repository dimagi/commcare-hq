window.angular.module('icdsApp').filter('indiaNumbers', function() {
    return function(number) {
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
});
