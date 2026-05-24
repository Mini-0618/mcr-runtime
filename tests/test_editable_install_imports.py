"""
test_editable_install_imports.py — MCR v0.9.5
Verify all runtime modules are importable after editable install.
"""
import importlib, sys, types


def test_runtime_package_importable():
    """Verify runtime package itself is importable."""
    import runtime
    assert isinstance(runtime, types.ModuleType)


def test_runtime_submodules_importable():
    """Verify all runtime submodules are importable."""
    modules = [
        "runtime.wal",
        "runtime.state",
        "runtime.reducer",
        "runtime.engine",
        "runtime.replay_verifier",
        "runtime.event_gate",
        "runtime.hermes_bridge",
    ]
    for name in modules:
        mod = importlib.import_module(name)
        assert isinstance(mod, types.ModuleType), f"Failed to import {name}"


def test_public_api_importable():
    """Verify public API symbols are accessible."""
    from runtime import (
        WAL,
        Event,
        SystemState,
        DeterministicReducer,
        ReplayVerifier,
        MCRRuntimeEngine,
        EventGate,
        HermesBridge,
    )
    # Just verify they are importable (truthy check)
    assert WAL
    assert Event
    assert SystemState
    assert DeterministicReducer
    assert ReplayVerifier
    assert MCRRuntimeEngine
    assert EventGate
    assert HermesBridge