import pytest

from foresight.extensions import (
    CapabilityGuard,
    PluginManager,
    PluginManifest,
    ScopeContext,
    ScopedToolRegistry,
    ToolDefinition,
)


def install_tool(
    manager: PluginManager,
    plugin_id: str,
    version: str,
    value: str,
    scope_key: str = "global",
):
    manifest = PluginManifest(plugin_id=plugin_id, version=version, kind="provider")

    def installer(context):
        context.register_tool(
            ToolDefinition("market_data", lambda: value, frozenset({"collector"}))
        )

    return manager.install(manifest, installer, scope_key=scope_key)


def test_scoped_shadowing_and_snapshot_pinning():
    registry = ScopedToolRegistry()
    registry.add_guard(
        CapabilityGuard("allow-market-data", allowed_tools=frozenset({"market_data"}))
    )
    manager = PluginManager(registry)
    scope = ScopeContext(tenant_id="default", preset_id="BR", task_id="task-1")

    install_tool(manager, "provider.market", "1.0.0", "v1")
    first_snapshot = manager.snapshot(scope, {"version": "policy-v1", "policy": {}})
    install_tool(manager, "provider.market", "2.0.0", "v2")

    assert registry.get("market_data", "collector", scope).handler() == "v2"
    pinned_id = first_snapshot.tools["market_data"]["registration_id"]
    assert registry.get("market_data", "collector", scope, pinned_id).handler() == "v1"

    install_tool(manager, "provider.market-br", "1.0.0", "br", "preset:default:br")
    assert registry.get("market_data", "collector", scope).handler() == "br"


def test_monotonic_guard_cannot_be_bypassed_by_local_tool():
    registry = ScopedToolRegistry()
    registry.add_guard(
        CapabilityGuard(
            "hard-deny",
            allowed_tools=frozenset({"market_data"}),
            reason="Hard runtime deny",
        )
    )
    registry.register(
        ToolDefinition("shell", lambda: "unsafe", frozenset({"collector"})),
        scope_key="task:task-1",
        plugin_id="tool.local-shell",
        plugin_version="1.0.0",
    )

    with pytest.raises(PermissionError, match="Hard runtime deny"):
        registry.get(
            "shell",
            "collector",
            ScopeContext(task_id="task-1"),
        )


def test_failed_staging_cleans_up_and_plugin_rollback_restores_previous_generation():
    registry = ScopedToolRegistry()
    manager = PluginManager(registry)
    scope = ScopeContext()

    manifest = PluginManifest("provider.broken", "1.0.0", "provider")
    with pytest.raises(RuntimeError, match="health check failed"):
        manager.install(
            manifest,
            lambda context: context.register_tool(ToolDefinition("broken", lambda: None)),
            health_check=lambda _context: False,
        )
    assert "broken" not in registry.snapshot(scope)

    install_tool(manager, "provider.market", "1.0.0", "v1")
    install_tool(manager, "provider.market", "2.0.0", "v2")
    restored = manager.rollback("provider.market")

    assert restored.manifest.version == "1.0.0"
    assert registry.get("market_data", "collector", scope).handler() == "v1"
