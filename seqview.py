#!/usr/bin/env python3

import abc
import collections.abc

__all__ = ['BidirectionalIndex', 'BidirectionalSequence',
           'succ', 'pred', 'begin', 'end',
           'smap', 'sfilter']

# TODO: reversed (and, for that matter, end) doesn't work right on
# map views over iterables of different lengths. In fact, in that
# case, the view isn't really bidirectional! We could make it work
# for the random-access view, but for bidirectional sequences, we
# have no way of knowing in advance which one is shortest and how
# much shorter it is than the others.

class BidirectionalIndex:
    """All of the operations on an index for a BidirectionalSequence.

    Concrete subclasses must provide __new__ or __init__,
    __succ__, __pred__, and __eq__.

    Note that because int values, and other types with __index__
    methods, do not provide __succ__ and __pred__, they are not
    instances of this type. The free functions succ and pred handle
    those cases."""
    __slots__ = ()
    @abc.abstractmethod
    def __succ__(self):
        raise IndexError
    @abc.abstractmethod
    def __pred__(self):
        raise IndexError        
    @abc.abstractmethod
    def __eq__(self, other):
        raise TypeError        
    def __ne__(self, other):
        return not self == other

def succ(index):
    """succ(index) -> index

    Returns the next index after the argument (index+1 for integers)."""
    try:
        return index.__succ__()
    except AttributeError:
        return index+1

def pred(index):
    """pred(index) -> index

    Returns the previous index before the argument (index-1 for integers)."""
    try:
        return index.__pred__()
    except AttributeError:
        if not index:
            raise ValueError('{} has no predecessor'.format(index))
        return index-1

# TODO: This should be a class, and a BidirectionalSequence in its own
# right, not an Iterator, right? Otherwise, it's useless, so scrap it.
def index_range(begin, end):
    while begin != end:
        yield begin
        begin = func(begin)

class BidirectionalSequence(collections.abc.Iterable,
                            collections.abc.Container):
    """All of the operations on a bidirectional-only sequence.

    Concrete classes must provide __new__ or __init__,
    __getitem__, __begin__, and __end__."""
    __slots__ = ()
    @abc.abstractmethod
    def __begin__(self):
        raise IndexError
    @abc.abstractmethod
    def __end__(self):
        raise IndexError        
    @abc.abstractmethod
    def __getitem__(self, index):
        raise IndexError
    def __contains__(self, value):
        return any(member == value for member in self)
    def __iter__(self):
        pos, end = self.__begin__(), self.__end__()
        try:
            while pos != end:
                yield self[pos]
                pos = succ(pos)
        except IndexError as e:
            raise StopIteration from e
    def __reversed__(self):
        begin, pos = self.__begin__(), self.__end__()
        while pos != begin:
            pos = pred(pos)
            yield self[pos]

def begin(seq):
    """begin(seq) -> index

    Returns the first index in the sequence. For bidirectional-only
    sequences this will usually be a special index type; for fully
    random-accessible sequences it will just be 0."""
    try:
        return seq.__begin__()
    except AttributeError:
        if isinstance(seq, collections.abc.Sequence):
            return 0
        raise

def end(seq):
    """end(seq) -> index

    Returns the index past the end of the sequence. For bidirectional-only
    sequences this will usually be a special index type; for fully
    random-accessible sequences it will just be len(seq)."""
    try:
        return seq.__end__()
    except AttributeError:
        if isinstance(seq, collections.abc.Sequence):
            return len(seq)
        raise

collections.abc.Sequence.__begin__ = lambda self: 0
collections.abc.Sequence.__end__ = collections.abc.Sequence.__len__
BidirectionalSequence.register(collections.abc.Sequence)

class MapBidirectionalView(BidirectionalSequence):            
    def __init__(self, func, *seqs):
        self.func, self.seqs = func, seqs
        class Index(BidirectionalIndex):
            def __init__(self, seqindices):
                self.seqindices = seqindices
            def __succ__(self):
                return Index([succ(seqindex) for seqindex in self.seqindices])
            def __pred__(self):
                return Index([pred(seqindex) for seqindex in self.seqindices])
            def __eq__(self, other):
                return (self.__class__ == other.__class__ and
                        self.seqindices == other.seqindices)
            def __repr__(self):
                return '{}({})'.format(self.__class__.__name__, self.seqindices)
        self.begin = Index([begin(seq) for seq in seqs])
        self.end = Index([end(seq) for seq in seqs])
    def __begin__(self):
        return self.begin
    def __end__(self):
        return self.end
    def __getitem__(self, index):
        try:
            si = zip(self.seqs, index.seqindices)
        except AttributeError:
            si = [(seq, index) for seq in self.seqs]
        if isinstance(index, slice):
            return self.__class__(self.func, *[seq[i] for seq, i in si])
        else:
            return self.func(*(seq[i] for seq, i in si))
    def __repr__(self):
        return '{}({}, {})'.format(
            self.__class__.__qualname__,
            self.func.__qualname__,
            ', '.join(map(repr, self.seqs)))

class MapView(MapBidirectionalView, collections.abc.Sequence):
    def __len__(self):
        return min(self.end)
    
def smap(func, *iterables):
    """smap(func, *iterables) -> view object or map object

    Make an iterator or a view with the result of computing the function
    using arguments from each of the iterables, stopping when the shortest
    iterable is exhausted. The function cannot be None.

    The result is a sequence if all inputs are sequences, a bidirectional-
    only sequence if all inputs are at least bidirectional sequences, an
    iterator otherwise. In any case, the values are computed lazily.
    """
    if all(isinstance(iterable, collections.abc.Sequence)
           for iterable in iterables):
        return MapView(func, *iterables)
    elif all(isinstance(iterable, BidirectionalSequence)
             for iterable in iterables):
        return MapBidirectionalView(func, *iterables)
    else:
        return map(func, *iterables)

class FilterBidirectionalView(BidirectionalSequence):            
    def __init__(self, func, seq):
        self.func, self.seq = func, seq
        class Index(BidirectionalIndex):
            def __init__(self, seqindex):
                self.seqindex = seqindex
            def __succ__(self):
                ret = Index(self.seqindex)
                while True:
                    ret.seqindex = succ(ret.seqindex)
                    if func(seq[ret.seqindex]):
                        return ret
            def __pred__(self):
                ret = Index(self.seqindex)
                while True:
                    ret.seqindex = pred(ret.seqindex)
                    if func(seq[ret.seqindex]):
                        return ret
            def __eq__(self, other):
                return (self.__class__ == other.__class__ and
                        self.seqindex == other.seqindex)
            def __repr__(self):
                return '{}({})'.format(self.__class__.__name__, self.seqindex)
        self.begin = Index(begin(seq))
        try:
            if not func(seq[self.begin.seqindex]):
                self.begin = succ(self.begin)
        except StopIteration:
            self.begin = self.end
        self.end = Index(end(seq))
    def __begin__(self):
        return self.begin
    def __end__(self):
        return self.end
    def __getitem__(self, index):
        if isinstance(index, slice):
            return self.__class__(self.func, self.seq[index])
        else:
            return self.seq[index.seqindex]
    def __repr__(self):
        return '{}({}, {!r})'.format(
            self.__class__.__qualname__,
            self.func.__qualname__,
            self.seq)

def sfilter(func, iterable):
    """sfilter(function, iterable) -> view object or map object

    Make an iterator or a view with those items of iterable for which
    function(item) is true. The function cannot be None.

    The result is a bidirectional- only sequence if all inputs are at
    least bidirectional sequences, an iterator otherwise. In either case,
    the values are computed lazily.
    """
    if isinstance(iterable, collections.abc.Sequence):
        return FilterBidirectionalView(func, iterable)
    else:
        return filter(func, iterable)

if __name__ == '__main__':
    s0 = (i for i in range(4))
    m0 = smap(lambda x: x*2, s0)
    print(m0, list(m0))
    s0 = (i for i in range(4))
    f0 = sfilter(lambda x: x%2, s0)
    print(f0, list(f0))
    
    s1 = [0, 1, 2, 3]
    m1 = smap(lambda x: x*2, s1)
    print(m1, list(m1), list(reversed(m1)))

    s2 = range(4)
    m2 = smap(lambda x: x*2, s2)
    print(m2, list(m2), list(reversed(m2)))

    f2 = sfilter(lambda x: x%2, s2)
    print(f2, list(f2), list(reversed(f2)))
    mf2 = smap(lambda x: x*2, f2)
    print(mf2, list(mf2), list(reversed(mf2)))

    m3 = smap(lambda x, y: x+y, s1, s2)
    print(m3, list(m3), list(reversed(m3)))

    m4 = smap(lambda x, y: x+y, s1, [10])
    print(m4, list(m4))#, list(reversed(m4)))

    m5 = smap(lambda x, y: x+y, [10], s1)
    print(m5, list(m5))#, list(reversed(m5)))
    
