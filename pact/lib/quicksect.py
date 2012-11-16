"""
Intersects ... faster.  Suports GenomicInterval datatype and multiple
chromosomes.


source:
http://bitbucket.org/james_taylor/bx-python/src/14b6a6c95da6/lib/bx/intervals/operations/quicksect.py
"""
import math
import time
import sys
import random

class IntervalTree( object ):
    def __init__( self ):
        self.chroms = {}
    def insert( self, interval, linenum=0, other=None ):
        chrom = interval.chrom
        start = interval.start
        end = interval.end
        if interval.chrom in self.chroms:
            self.chroms[chrom] = self.chroms[chrom].insert( start, end, linenum, other )
        else:
            self.chroms[chrom] = IntervalNode( start, end, linenum, other )
    def intersect( self, interval, report_func ):
        chrom = interval.chrom
        start = interval.start
        end = interval.end
        if chrom in self.chroms:
            self.chroms[chrom].intersect( start, end, report_func )
    def traverse( self, func ):
        for item in self.chroms.itervalues():
            item.traverse( func )

class IntervalNode( object ):
    def __init__( self, start, end, linenum=0, other=None ):
        # Python lacks the binomial distribution, so we convert a
        # uniform into a binomial because it naturally scales with
        # tree size.  Also, python's uniform is perfect since the
        # upper limit is not inclusive, which gives us undefined here.
        #self.priority = math.ceil( (-1.0 / math.log(.5)) * math.log( -1.0 / (random.uniform(0,1) - 1)))
        self.priority=1
        self.start = start
        self.end = end
        self.maxend = self.end
        self.minend = self.end
        self.left = None
        self.right = None
        self.linenum = linenum
        self.other = other
    def insert( self, start, end, linenum=0, other=None ):
        root = self
        if start > self.start:
            # insert to right tree
            if self.right:
                self.right = self.right.insert( start, end, linenum, other )
            else:
                self.right = IntervalNode(start, end, linenum, other )
            # rebalance tree
            if self.priority < self.right.priority:
                root = self.rotateleft()
        else:
            # insert to left tree
            if self.left:
                self.left = self.left.insert( start, end, linenum, other )
            else:
                self.left = IntervalNode(start, end, linenum, other )
            # rebalance tree
            if self.priority < self.left.priority:
                root = self.rotateright()
        if root.right and root.left: 
            root.maxend = max( root.end, root.right.maxend, root.left.maxend )
            root.minend = min( root.end, root.right.minend, root.left.minend )
        elif root.right: 
            root.maxend = max( root.end, root.right.maxend )
            root.minend = min( root.end, root.right.minend )
        elif root.left:
            root.maxend = max( root.end, root.left.maxend )
            root.minend = min( root.end, root.left.minend )
        return root

    def rotateright( self ):
        print "rotate right"
        root = self.left
        self.left = self.left.right
        root.right = self
        if self.right and self.left: 
            self.maxend = max(self.end, self.right.maxend, self.left.maxend)
            self.minend = min(self.end, self.right.minend, self.left.minend )
        elif self.right:
            self.maxend = max(self.end, self.right.maxend)
            self.minend = min(self.end, self.right.minend)
        elif self.left:
            self.maxend = max(self.end, self.left.maxend)
            self.minend = min(self.end, self.left.minend )
        return root
        
    def rotateleft( self ):
        print "rotate left"
        root = self.right
        self.right = self.right.left
        root.left = self
        if self.right and self.left: 
            self.maxend = max(self.end, self.right.maxend, self.left.maxend)
            self.minend = min(self.end, self.right.minend, self.left.minend )
        elif self.right:
            self.maxend = max(self.end, self.right.maxend)
            self.minend = min(self.end, self.right.minend)
        elif self.left:
            self.maxend = max(self.end, self.left.maxend)
            self.minend = min(self.end, self.left.minend )
        return root

    def intersect( self, start, end, report_func ):
        if start < self.end and end > self.start: report_func( self )
        if self.left and start < self.left.maxend:
            self.left.intersect( start, end, report_func )
        if self.right and end > self.start:
            self.right.intersect( start, end, report_func )

    def traverse( self, func ):
        if self.left: self.left.traverse( func )
        func( self )
        if self.right: self.right.traverse( func )

def main():
    test = None
    intlist = []
    for x in range(20000):
        start = random.randint(0,1000000)
        end = start + random.randint(1, 1000)
        if test: test = test.insert( start, end )
        else: test = IntervalNode( start, end )
        intlist.append( (start, end) )
    starttime = time.clock()
    for x in range(5000):
        start = random.randint(0, 10000000)
        end = start + random.randint(1, 1000)
        result = []
        test.intersect( start, end, lambda x: result.append(x.linenum) )
    print "%f for tree method" % (time.clock() - starttime)
    starttime = time.clock()
    for x in range(5000):
        start = random.randint(0, 10000000)
        end = start + random.randint(1, 1000)
        bad_sect( intlist, start, end)
    print "%f for linear (bad) method" % (time.clock() - starttime)

def test_func( node ):
    print "[%d, %d), %d" % (node.start, node.end, node.maxend)

def bad_sect( lst, int_start, int_end ):
    intersection = []
    for start, end in lst:
        if int_start < end and int_end > start:
            intersection.append( (start, end) )
    return intersection

if __name__ == "__main__":
    main()


