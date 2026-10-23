from unittest.mock import patch

import pytest
from django.core.management import call_command
from testil import Config

from pillowtop.const import DEFAULT_PROCESSOR_CHUNK_SIZE

COMMAND = 'pillowtop.management.commands.run_ptop'


@pytest.mark.parametrize("args, chunk_size", [
    ([], DEFAULT_PROCESSOR_CHUNK_SIZE),
    (['--processor-chunk-size=1'], 1),
])
def test_run_all_passes_processor_chunk_size(args, chunk_size):
    configs = [
        Config(get_instance=lambda **kw: ('pillow1', kw)),
        Config(get_instance=lambda **kw: ('pillow2', kw)),
    ]
    with (
        patch(f'{COMMAND}.get_all_pillow_configs', return_value=configs),
        patch(f'{COMMAND}.start_pillows') as start_pillows,
    ):
        call_command('run_ptop', '--all', *args)

    start_pillows.assert_called_once_with(pillows=[
        ('pillow1', {'processor_chunk_size': chunk_size}),
        ('pillow2', {'processor_chunk_size': chunk_size}),
    ])
