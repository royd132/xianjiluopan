import pytest

from foresight.extensions import (
    CapabilityGuard,
    PluginManager,
    PluginManifest,
    ScopeContext,
    ToolDefinition,
    ToolRegistry,
)


def test_tool_registration_and_retrieval():
    registry = ToolRegistry()
    registry.register(
        ToolDefinition("market_data", lambda: "v1", frozenset({"collector"}))
    )
    definition = registry.get("market_data", "collector")
    assert definition.handler() == "v1"

    with pytest.raises(PermissionError, match="cannot use tool"):
        registry.get("market_data", "unauthorized-agent")

    with pytest.raises(KeyError, match="Unknown tool"):
        registry.get("nonexistent", "collector")


def test_guard_blocks_unregistered_tools():
    registry = ToolRegistry()
    registry.add_guard(
        CapabilityGuard(
            "allow-market-only",
            allowed_tools=frozenset({"market_data"}),
            reason="Hard runtime deny",
        )
    )
    registry.register(
        ToolDefinition("market_data", lambda: "ok", frozenset({"collector"}))
    )
    registry.register(
        ToolDefinition("shell", lambda: "unsafe", frozenset({"collector"}))
    )

    assert registry.get("market_data", "collector").handler() == "ok"
    with pytest.raises(PermissionError, match="Hard runtime deny"):
        registry.get("shell", "collector")


def test_failed_plugin_install_cleans_up_tools():
    registry = ToolRegistry()
    manager = PluginManager(registry)

    manifest = PluginManifest("provider.broken", "1.0.0", "provider")
    with pytest.raises(RuntimeError, match="health check failed"):
        manager.install(
            manifest,
            lambda ctx: ctx.register_tool(ToolDefinition("broken", lambda: None)),
            health_check=lambda _ctx: False,
        )
    assert registry.snapshot() == {}


def test_plugin_install_and_snapshot():
    registry = ToolRegistry()
    manager = PluginManager(registry)

    manifest = PluginManifest("provider.market", "1.0.0", "provider")

    def installer(ctx):
        ctx.register_tool(
            ToolDefinition("market_data", lambda: "v1", frozenset({"collector"}))
        )

    result = manager.install(manifest, installer)
    assert result["status"] == "active"
    assert result["plugin_id"] == "provider.market"

    scope = ScopeContext(task_id="task-1")
    snapshot = manager.snapshot(scope, {"version": "v1", "policy": {}})
    assert snapshot.scope == {"task_id": "task-1"}
    assert "market_data" in snapshot.tools
    assert len(snapshot.plugins) == 1
