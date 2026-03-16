"""Tests for hook.py — plugin enable() entry point."""
import sys
import types
from unittest.mock import AsyncMock, MagicMock, call

import pytest

# conftest stubs are already installed
from app.compass_svc import CompassService


# ===================================================================
# hook module attributes
# ===================================================================

class TestHookAttributes:
    def test_name(self):
        from hook import name
        assert name == "Compass"

    def test_description(self):
        from hook import description
        assert isinstance(description, str)
        assert len(description) > 0

    def test_address(self):
        from hook import address
        assert address == "/plugin/compass/gui"


# ===================================================================
# enable()
# ===================================================================

class TestEnable:
    @pytest.fixture
    def mock_app_services(self):
        app = MagicMock()
        router = MagicMock()
        app.router = router

        app_svc = MagicMock()
        app_svc.application = app

        services = {
            "app_svc": app_svc,
            "data_svc": AsyncMock(),
            "rest_svc": AsyncMock(),
            "auth_svc": AsyncMock(),
        }
        return services, app, router

    @pytest.mark.asyncio
    async def test_registers_three_routes(self, mock_app_services):
        from hook import enable
        services, app, router = mock_app_services
        await enable(services)
        assert router.add_route.call_count == 3

    @pytest.mark.asyncio
    async def test_layer_route_registered(self, mock_app_services):
        from hook import enable
        services, app, router = mock_app_services
        await enable(services)

        calls = router.add_route.call_args_list
        paths = [(c[0][0], c[0][1]) for c in calls]
        assert ("POST", "/plugin/compass/layer") in paths

    @pytest.mark.asyncio
    async def test_adversary_route_registered(self, mock_app_services):
        from hook import enable
        services, app, router = mock_app_services
        await enable(services)

        calls = router.add_route.call_args_list
        paths = [(c[0][0], c[0][1]) for c in calls]
        assert ("POST", "/plugin/compass/adversary") in paths

    @pytest.mark.asyncio
    async def test_gui_route_registered(self, mock_app_services):
        from hook import enable
        services, app, router = mock_app_services
        await enable(services)

        calls = router.add_route.call_args_list
        paths = [(c[0][0], c[0][1]) for c in calls]
        assert ("GET", "/plugin/compass/gui") in paths

    @pytest.mark.asyncio
    async def test_handlers_are_bound_methods(self, mock_app_services):
        from hook import enable
        services, app, router = mock_app_services
        await enable(services)

        calls = router.add_route.call_args_list
        for c in calls:
            handler = c[0][2]
            # Each handler should be a bound method of a CompassService instance
            assert hasattr(handler, "__self__")
            assert type(handler.__self__).__name__ == "CompassService"

    @pytest.mark.asyncio
    async def test_compass_service_receives_services(self, mock_app_services):
        from hook import enable
        services, app, router = mock_app_services
        await enable(services)

        # Get the CompassService instance from any registered handler
        handler = router.add_route.call_args_list[0][0][2]
        svc = handler.__self__
        assert svc.services is services
