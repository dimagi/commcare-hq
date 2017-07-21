window.angular.module('icdsApp').filter('indiaNumbers', function() {
    return function(number) {
        number=number.toString();
        var lastThree = number.substring(number.length-3);
        var otherNumbers = number.substring(0,number.length-3);
        if(otherNumbers !== '')
            lastThree = ',' + lastThree;
        var res = otherNumbers.replace(/\B(?=(\d{2})+(?!\d))/g, ",") + lastThree;

        return res;
    };
});
