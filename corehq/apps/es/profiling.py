from dataclasses import dataclass, field
from corehq.util.timer import TimingContext
from corehq.apps.es.es_query import HQESQuery


@dataclass
class ESQueryProfiler:
    """
    A profiler for gathering timing and profiling data on functions that may or may not contain
    Elasticsearch queries.

    This is particularly useful for profiling workflows involving multiple ES queries
    and other operations. For profiling a single ES query, you can simply use `query.enable_profiling`.
    However, when profiling a broader workflow, the outermost `with timing_context` block
    should be chosen carefully, as it represents the total evaluation time being measured.

    Attributes:
        search_class (HQESQuery): The ES query class to be profiled (any subclass of HQESQuery).
        name (str): A label for the profiler instance, defaults to 'Query Profiler'.
        debug_mode (bool): Enables ES profiling details when set to True.
        queries (list): Stores profiling data for individual queries when in debug mode.
        _query_number (int): Tracks the number of queries executed within the profiler.

    Methods:
        get_search_class(slug=None): Returns a wrapped version of the search class
            that automatically profiles query execution times.
    """

    search_class: HQESQuery = HQESQuery
    name: str = 'Query Profiler'
    debug_mode: bool = False
    queries: list = field(default_factory=list)
    _query_number: int = 0

    def __post_init__(self):
        self.timing_context = TimingContext(self.name)

    def get_search_class(self, slug=None):
        profiler = self

        class ProfiledSearchClass(self.search_class):
            def run(self):
                profiler._query_number += 1
                if profiler.debug_mode:
                    self.es_query['profile'] = True

                tc = profiler.timing_context(f'run query #{profiler._query_number}: {slug}')
                timer = tc.peek()
                with tc:
                    results = super().run()

                if profiler.debug_mode:
                    profiler.queries.append({
                        'slug': slug,
                        'query_number': profiler._query_number,
                        'query': self.raw_query,
                        'duration': timer.duration,
                        'profile_json': results.raw.pop('profile'),
                    })
                return results

        return ProfiledSearchClass
