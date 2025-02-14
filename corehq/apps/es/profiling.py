from dataclasses import dataclass, field
from corehq.util.timer import TimingContext
from corehq.apps.es.es_query import HQESQuery


@dataclass
class ESQueryProfiler:
    """
    Allows a user to profile ES queries. The timing_context also allows for adding timing blocks
    to arbitrary parts of code which will be included in the final timing output.
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
