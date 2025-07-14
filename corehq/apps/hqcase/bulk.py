from contextlib import contextmanager
from dataclasses import dataclass

from casexml.apps.case.mock import CaseBlock
from corehq.apps.users.util import SYSTEM_USER_ID, username_to_user_id
from corehq.form_processor.models import CommCareCase

from .utils import CASEBLOCK_CHUNKSIZE, submit_case_blocks


@dataclass(frozen=True)
class SystemFormMeta:
    user_id: str = SYSTEM_USER_ID
    username: str = SYSTEM_USER_ID
    device_id: str = SYSTEM_USER_ID

    @classmethod
    def for_script(cls, name, username=None):
        user_kwargs = {}
        if username:
            user_id = username_to_user_id(username)
            if not user_id:
                raise Exception(f"User '{username}' not found")
            user_kwargs = {
                'user_id': user_id,
                'username': username,
            }

        return cls(
            device_id=name,
            **user_kwargs,
        )


def update_cases(domain, update_fn, case_ids, form_meta: SystemFormMeta = None):
    """
    Perform a large number of case updates in chunks

    update_fn should be a function which accepts a case and returns a list of CaseBlock objects
    if an update is to be performed, or None to skip the case.

    Returns counts of number of updates made (not necessarily number of cases update).
    """
    cases = CommCareCase.objects.iter_cases(case_ids)
    case_blocks = (
        case_block for case in cases
        for case_block in (update_fn(case) or [])
    )
    form_meta = form_meta or SystemFormMeta()
    count = 0
    with submit_case_block_context(
        domain,
        device_id=form_meta.device_id,
        user_id=form_meta.user_id,
        username=form_meta.username,
    ) as submit_case_block:
        for count, case_block in enumerate(case_blocks, start=1):
            submit_case_block.send(case_block)
    return count


def coro_as_context(func):
    """
    Decorator to transform a coroutine function into a context manager.

    The context manager primes the coroutine using ``next()`` when
    entering the context, and calls ``.close()`` when exiting the context.

    Usage::

        @coro_as_context
        def my_coro():
            try:
                while True:
                    data = yield
                    ... # Do something with data
            except GeneratorExit:
                ... # Cleanup

        with my_coro() as coro:
            coro.send(data)

    """
    @contextmanager
    def wrapper(*args, **kwargs):
        coro = func(*args, **kwargs)
        next(coro)  # Prime the coroutine
        try:
            yield coro
        finally:
            coro.close()
    return wrapper


def submit_case_block_coro(
    *args,
    chunk_size=CASEBLOCK_CHUNKSIZE,
    **kwargs,
):
    """
    Accepts case blocks and submits them in chunks of chunk_size.
    Returns a list of form IDs.

    Use undecorated as a coroutine for access to the return value, or
    use `submit_case_block_context()` for simplicity.

    Context manager usage::

        with submit_case_block_context(domain, device_id=__name__) as submit:
            for case in iter_all_the_cases:
                case_block = get_case_updates(case)
                submit.send(case_block)

    Coroutine usage::

        submit = submit_case_block_coro(domain, device_id=__name__)
        next(submit)  # Prime the coroutine
        for case in iter_all_the_cases:
            case_block = get_case_updates(case)
            submit.send(case_block)
        try:
            submit.send(None)  # Trigger exit
        except StopIteration as exc:
            form_ids = exc.value

    """
    form_ids = []
    case_blocks = []
    try:
        while True:
            case_block = yield
            if case_block is None:  # Send `None` to exit
                raise GeneratorExit
            case_blocks.append(
                case_block.as_text()
                if isinstance(case_block, CaseBlock)
                else case_block
            )
            if len(case_blocks) >= chunk_size:
                chunk = case_blocks[:chunk_size]
                case_blocks = case_blocks[chunk_size:]
                xform, __ = submit_case_blocks(chunk, *args, **kwargs)
                form_ids.append(xform.form_id)
    except GeneratorExit:
        if case_blocks:
            xform, __ = submit_case_blocks(case_blocks, *args, **kwargs)
            form_ids.append(xform.form_id)
    return form_ids


submit_case_block_context = coro_as_context(submit_case_block_coro)
