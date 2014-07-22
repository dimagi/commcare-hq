/*
    Implemented (I think) directly from the pseudocode at
    http://en.wikipedia.org/wiki/Longest_common_substring_problem
 */
function lcsMerge(X, Y, isEqual) {
    'use strict';
    isEqual = isEqual || function (a, b) {
        return a === b;
    };
    var cache = {};
    function recLcsMerge(i, j) {
        var val, val1, val2, recur = recLcsMerge, cache_key = i + ' ' + j;
        if (cache[cache_key]) {
            return cache[cache_key];
        }
        if (i === 0 && j === 0) {
            val = {
                lcs_length: 0,
                merge: []
            };
        } else if (i === 0) {
            val = recur(i, j - 1);
            val.merge.push({x: false, y: true, token: Y[j - 1]});
        } else if (j === 0) {
            val = recur(i - 1, j);
            val.merge.push({x: true, y: false, token: X[i - 1]});
        } else if (isEqual(X[i - 1], Y[j - 1])) {
            val = recur(i - 1, j - 1);
            val.lcs_length++;
            val.merge.push({x: true, y: true, token: X[i - 1]});
        } else {
            val1 = recur(i, j - 1);
            val2 = recur(i - 1, j);
            if (val2.lcs_length > val1.lcs_length) {
                val = val2;
                val.merge.push({x: true, y: false, token: X[i - 1]});
            } else {
                val = val1;
                val.merge.push({x: false, y: true, token: Y[j - 1]});
            }
        }
        cache[cache_key] = {
            lcs_length: val.lcs_length,
            merge: val.merge.slice(0)
        };
        return val;
    }

    return recLcsMerge(X.length, Y.length).merge;
}
