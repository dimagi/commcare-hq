class QueryableList(list):
    def __getattr__(self, item):
        #  __getattr__ is only called when other attribute lookup methods fail.
        if item.find('__') != -1:
            fn = item.split("__")
            fs = []
            for i in fn:
                fq = self.__getattribute__("_" + i.replace('not_',''))
                if i.startswith('not_'):
                    fr = lambda x: not fq(x)
                else:
                    fr = fq
                fs += [fr]
            return filter(reduce(lambda x,y: (lambda(z): x(z) and y(z)), fs), self)
        elif not item.startswith('_'):
            if item.startswith('not_'):
                return filter(lambda x: not self.__getattribute__("_" + item.replace('not_', ''))(x), self)
            else:
                return filter(self.__getattribute__("_" + item), self)
        else:
            raise AttributeError

class ExampleQueryableList(QueryableList):
    '''
    QueryableSets have all the attributes of sets:

    >>> q = ExampleQueryableList()
    >>> q += range(0,20)
    >>> len(q)
    20

    They also have an associated set of predicates, which act as
    filters on the data.  Predicates are functions of one variable
    which return a boolean.  They act like attributes; to retrieve
    one, just specify its name (without the _):

    >>> q.even
    [0, 2, 4, 6, 8, 10, 12, 14, 16, 18]

    Prepending not_ to the name of a predicate inverts the sense:

    >>> q.not_even
    [1, 3, 5, 7, 9, 11, 13, 15, 17, 19]
    
    You can chain predicates with double underscores, '__' :

    >>> q.even__div_three
    [0, 6, 12, 18]

    This works with inversion as well:
    
    >>> q.even__not_div_three
    [2, 4, 8, 10, 14, 16]

    You can define new predicates on an existing instance:

    >>> q._div_four = lambda x: x%4 == 0
    >>> q.div_three__div_four
    [0, 12]
    '''
    def __init__(self):
        self._even = lambda x: x%2 == 0
        self._div_three = lambda x: x%3 == 0

if __name__ == "__main__":
    import doctest
    doctest.testmod()
