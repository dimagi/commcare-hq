# Experiments Framework for Comparing Old and New Code Paths

The Experiments framework allows performance and results comparisons of old and
new code paths. This is useful for testing new implementations against existing
ones to ensure they perform as expected before adopting the new implementation.

Inspired by [Github Scientist](https://github.blog/developer-skills/application-development/scientist/).

## Features

- **Performance Recording**: The framework records execution times and sends
  `commcare.experiment` metrics to Datadog. When metrics are enabled for only
  the old or new code path, timing of the respective code path is recorded along
  with an `enabled` tag value of `old` or `new`. When `both` are enabled, an
  additional "diff" metric is recorded with the duration of the new code path as
  a percentage of the old code path time.
- **Result Comparison**: It compares the results of the old and new code paths
  and logs unexpected differences to Sentry. The comparison can be customized
  by passing an `is_equal` callable to the experiment decorator.
- **Experiment Management**: Experiments can be enabled or disabled using
  `ExperimentEnabler` records in Django Admin. All experiments are disabled by
  default, meaning only the old code path is run until `enabled_percent` is set
  to a value greater than zero. See `enabled_percent` docs for more details on
  fine-grained experiment control. Enabled states are cached, so changes in
  Django Admin may not apply immediately. 

## Usage

To define an experiment, use the `Experiment` class to create a decorator for
the function you want to test.

```python
from corehq.apps.experiments import Experiment, MOON_SHOT

experiment = Experiment(
    campaign=MOON_SHOT,
    old_args={"feature": "valley"},
    new_args={"feature": "crater"},
)

@experiment
def function(other, args, *, feature):
    ... # implementation
```
