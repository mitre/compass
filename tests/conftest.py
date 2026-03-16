"""Shared fixtures for compass plugin tests."""
import json
import sys
import types
import uuid
from enum import Enum
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Stub aiohttp_jinja2 if not installed (template decorator)
# ---------------------------------------------------------------------------

if "aiohttp_jinja2" not in sys.modules:
    _aiohttp_jinja2 = types.ModuleType("aiohttp_jinja2")

    def _template(name):
        def decorator(func):
            return func
        return decorator

    _aiohttp_jinja2.template = _template
    sys.modules["aiohttp_jinja2"] = _aiohttp_jinja2


# Now safe to import — app/ has real stub files for auth_svc
from app.compass_svc import CompassService  # noqa: E402


# ---------------------------------------------------------------------------
# Tiny domain objects that mimic Caldera's internal models
# ---------------------------------------------------------------------------

class FakeAbility:
    """Minimal ability stand-in returned by data_svc.locate."""

    def __init__(self, ability_id="ab-1", technique_id="T1059", tactic="execution", name="Test"):
        self.ability_id = ability_id
        self.technique_id = technique_id
        self.tactic = tactic
        self.name = name
        self.display = dict(
            ability_id=ability_id,
            technique_id=technique_id,
            tactic=tactic,
            name=name,
        )


class FakeAdversary:
    """Minimal adversary stand-in."""

    def __init__(self, adversary_id="adv-1", name="TestAdv", description="desc",
                 atomic_ordering=None):
        self.adversary_id = adversary_id
        self.name = name
        self.description = description
        self.atomic_ordering = atomic_ordering or []
        self.display = dict(
            adversary_id=adversary_id,
            name=name,
            description=description,
            atomic_ordering=self.atomic_ordering,
        )


# ---------------------------------------------------------------------------
# Service mocks
# ---------------------------------------------------------------------------

class FakeAccess(Enum):
    RED = "red"


@pytest.fixture
def mock_services():
    """Build a dict of mock Caldera services."""
    data_svc = AsyncMock()
    rest_svc = AsyncMock()
    auth_svc = AsyncMock()
    app_svc = MagicMock()

    rest_svc.Access = FakeAccess

    services = {
        "data_svc": data_svc,
        "rest_svc": rest_svc,
        "auth_svc": auth_svc,
        "app_svc": app_svc,
    }
    return services


@pytest.fixture
def compass_svc(mock_services):
    """Return a CompassService wired to mock services."""
    return CompassService(mock_services)


@pytest.fixture
def sample_abilities():
    """A small set of fake abilities."""
    return [
        FakeAbility("ab-1", "T1059", "execution", "PowerShell"),
        FakeAbility("ab-2", "T1059.001", "execution", "PowerShell subtech"),
        FakeAbility("ab-3", "T1071", "command-and-control", "App Layer Protocol"),
    ]


@pytest.fixture
def sample_adversaries(sample_abilities):
    """A small set of fake adversaries."""
    return [
        FakeAdversary(
            adversary_id="adv-1",
            name="TestAdv",
            description="test adversary",
            atomic_ordering=[a.display for a in sample_abilities[:2]],
        ),
    ]


@pytest.fixture
def valid_layer_json():
    """A valid ATT&CK Navigator layer body."""
    return {
        "version": "3.0",
        "name": "TestLayer",
        "description": "A test layer",
        "domain": "mitre-enterprise",
        "techniques": [
            {"techniqueID": "T1059", "tactic": "execution", "score": 1,
             "color": "", "comment": "", "enabled": True},
            {"techniqueID": "T1071", "tactic": "command-and-control", "score": 1,
             "color": "", "comment": "", "enabled": True},
            {"techniqueID": "T1000", "tactic": "skipped", "score": 0,
             "color": "", "comment": "", "enabled": True},
        ],
        "legendItems": [],
        "gradient": {"colors": ["#ffffff", "#66ff66"], "minValue": 0, "maxValue": 1},
    }


@pytest.fixture
def empty_layer_json():
    """Layer with no techniques."""
    return {
        "version": "3.0",
        "name": "EmptyLayer",
        "description": "Empty",
        "domain": "mitre-enterprise",
        "techniques": [],
    }


@pytest.fixture
def layer_missing_fields():
    """Layer missing name and description."""
    return {
        "techniques": [
            {"techniqueID": "T1059", "tactic": "execution", "score": 1},
        ],
    }


@pytest.fixture
def layer_no_tactic():
    """Layer with technique missing tactic field."""
    return {
        "name": "NoTactic",
        "description": "test",
        "techniques": [
            {"techniqueID": "T1059", "score": 1},
        ],
    }
