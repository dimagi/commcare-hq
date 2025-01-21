import time
from functools import partial, wraps
from operator import eq

from dimagi.utils.logging import notify_error, notify_exception

from corehq.util.metrics import metrics_histogram


def experiment(
    func=None,
    /,
    campaign=None,
    path=None,
    old_args=None,
    new_args=None,
    is_equal=eq,
    time_buckets=(0.01, 0.1, 1, 10, 100),
    percent_buckets=(50, 95, 105, 200),
):
    """Experiment decorator for comparing old and new code paths.

    :param campaign: Experiment campaign name for a group of experiments.
    :param path: Module path. Example: 'corehq.apps.science'.
    :param old_args: A dict of arguments to invoke the old code path.
    :param new_args: A dict of arguments to invoke the new code path.
    :param time_buckets: A tuple of histogram buckets for the old code
        path timer.
    :param percent_buckets: A tuple of histogram buckets for the new
        code path time as a percentage of the old code path time. For
        example, if the old code path takes 1 second and the new code
        path takes 2 seconds, the percentage is 2 / 1 or 200%.
    """
    if func is None:
        return partial(
            experiment,
            campaign=campaign,
            path=path,
            old_args=old_args,
            new_args=new_args,
            is_equal=is_equal,
            time_buckets=time_buckets,
            percent_buckets=percent_buckets,
        )
    if campaign is None:
        raise ValueError("campaign is required")
    if path is None:
        raise ValueError("path is required")
    old_args = old_args or {}
    new_args = new_args or {}
    tags = {"campaign": campaign, "path": f"{path}.{func.__name__}"}
    over_the_top = percent_buckets[-1] + 1

    def describe(args, kwargs):
        def rep(v):
            rval = repr(v)
            return (rval[:80] + "...") if len(rval) > 80 else rval
        argv = [rep(a) for a in args] + [f"{k}={rep(v)}" for k, v in kwargs.items()]
        return f"{func.__name__}({', '.join(argv)})"

    @wraps(func)
    def wrapper(*args, **kwargs):
        old_error = new_error = None
        start = time.time()
        try:
            old_result = func(*args, **kwargs, **old_args)
        except Exception as err:
            old_error = err
        mid = time.time()
        try:
            new_result = func(*args, **kwargs, **new_args)
        except Exception as err:
            if old_error is None:
                notify_exception(None, "new code path failed in experiment",
                                details={"campaign": campaign, "path": path})
                new_error = True  # error reference not needed
            else:
                new_error = err

        end = time.time()
        old_time = mid - start
        new_time = end - mid
        print(old_time, new_time)
        diff_pct = (new_time / old_time * 100) if old_time else over_the_top
        metrics_histogram(
            "commcare.science.time", old_time, tags=tags,
            bucket_tag='duration', buckets=time_buckets, bucket_unit='s',
        )
        metrics_histogram(
            "commcare.science.diff", diff_pct, tags=tags,
            bucket_tag='percent', buckets=percent_buckets, bucket_unit='%',
        )

        if old_error is not None:
            if new_error is None:
                new_repr = repr(new_result)
            elif type(new_error) is type(old_error) and new_error.args == old_error.args:
                raise old_error
            else:
                new_repr = f"raised {type(new_error).__name__}({str(new_error)!r})"
            old_repr = f"{type(old_error).__name__}({str(old_error)!r})"
            notify_error(
                f"{describe(args, kwargs)}: raised {old_repr} != {new_repr}",
                details={"campaign": campaign, "path": path},
            )
            raise old_error
        if new_error is None and not is_equal(old_result, new_result):
            notify_error(
                f"{describe(args, kwargs)}: {old_result!r} != {new_result!r}",
                details={"campaign": campaign, "path": path},
            )
        return old_result
    return wrapper
