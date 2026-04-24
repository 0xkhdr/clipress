import os
import pytest


@pytest.fixture
def fixtures_dir():
    return os.path.join(os.path.dirname(__file__), "fixtures")


def load_fixture(fixtures_dir, filename):
    with open(os.path.join(fixtures_dir, filename), "r", encoding="utf-8") as f:
        return f.read()
