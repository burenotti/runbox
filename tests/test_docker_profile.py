from pathlib import Path

import pytest

from runbox.models import DockerProfile, File
from runbox.utils import _


@pytest.fixture
def files():
    return [
        File(
            name='main.cpp',
            content=b'',
        ),
        File(
            name='class.h',
            content=b'',
        ),

        File(
            name='class.cpp',
            content=b'',
        ),
    ]


@pytest.fixture(scope='function')
def profile():
    return DockerProfile(
        image='ubuntu:latest',
        user='root',
        workdir=Path('/sandbox'),
        cmd_template=[]
    )


def test_ellipsis_between(profile, files):
    profile = profile.copy(update={'cmd_template': ['g++', ..., '-o', 'build']})
    assert profile.cmd(files) == ['g++', 'main.cpp', 'class.h', 'class.cpp', '-o', 'build']


def test_ellipsis_end(profile, files):
    profile = profile.copy(update={'cmd_template': ['g++', ...]})
    assert profile.cmd(files) == ['g++', 'main.cpp', 'class.h', 'class.cpp']


def test_placeholder_shuffling(profile, files):
    profile = profile.copy(update={'cmd_template': ['g++', _[0], _[2], _[1]]})
    assert profile.cmd(files) == ['g++', 'main.cpp', 'class.cpp', 'class.h']


def test_placeholder_with_ellipsis(profile, files):
    files.append(File(name='/build', content=b''))
    profile = profile.copy(update={'cmd_template': ['g++', ..., '-o', _[-1]]})
    assert profile.cmd(files) == ['g++', 'main.cpp', 'class.h', 'class.cpp', '-o', '/build']


def test_placeholder_unbound_error(profile, files):
    profile = profile.copy(update={'cmd_template': ['g++', _[42]]})
    with pytest.raises(ValueError):
        profile.cmd(files)
