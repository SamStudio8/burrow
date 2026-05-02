import json
from pathlib import Path
import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def example_request():
    return json.loads((FIXTURES / "request.json").read_text())


@pytest.fixture
def example_response():
    return json.loads((FIXTURES / "response.json").read_text())


def pytest_addoption(parser):
    parser.addoption(
        "--rule",
        action="store",
        nargs="+",
        metavar="SLUG",
        help="only run tests matching the rule slug SLUG.",
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "rule(name): mark test to match given rule slug."
    )


def pytest_runtest_setup(item):
    selected_rules = item.config.getoption("--rule")
    if not selected_rules:
        return

    rules = [mark.args[0] for mark in item.iter_markers(name="rule")]
    if not rules:
        pytest.skip(f"test is not marked with rule({selected_rules!r})")
    if not any(rule in rules for rule in selected_rules):
        pytest.skip(f"test requires rule in {rules!r}")
