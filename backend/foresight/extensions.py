from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import uuid4

from .harness import stable_hash, utc_now

PLUGIN_ID = re.compile(r"[a-z0-9][a-z0-9._-]{1,79}")


@dataclass(frozen=True, slots=True)
class ScopeContext:
    """Per-task scope. Tenant/preset removed — single-tenant demo."""

    task_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"task_id": self.task_id}

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ScopeContext":
        return cls(task_id=value.get("task_id"))


@dataclass(frozen=True, slots=True)
class PluginManifest:
    plugin_id: str
    version: str
    kind: str
    description: str = ""
    capabilities: tuple[str, ...] = ()
    permissions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not PLUGIN_ID.fullmatch(self.plugin_id):
            raise ValueError(f"Invalid plugin id: {self.plugin_id}")
        if not self.version.strip():
            raise ValueError("Plugin version is required")
        if self.kind not in {"provider", "tool", "agent", "evaluator", "policy-pack"}:
            raise ValueError(f"Unsupported plugin kind: {self.kind}")

    @property
    def identity(self) -> str:
        return f"{self.plugin_id}@{self.version}"

    @property
    def digest(self) -> str:
        return stable_hash(self.as_dict(include_digest=False))

    def as_dict(self, include_digest: bool = True) -> dict[str, Any]:
        value = {
            "plugin_id": self.plugin_id,
            "version": self.version,
            "kind": self.kind,
            "description": self.description,
            "capabilities": list(self.capabilities),
            "permissions": list(self.permissions),
        }
        if include_digest:
            value["digest"] = self.digest
        return value


@dataclass(slots=True)
class ToolDefinition:
    name: str
    handler: Callable[..., Any]
    allowed_agents: frozenset[str] = frozenset()
    timeout_seconds: float = 20.0
    description: str = ""


@dataclass(frozen=True, slots=True)
class CapabilityGuard:
    """Allowlist-only guard. Deny fields removed — never populated."""

    guard_id: str
    allowed_tools: frozenset[str] | None = None
    reason: str = "Capability denied by runtime policy"

    def check(self, tool_name: str, agent: str) -> tuple[bool, str]:
        if self.allowed_tools is not None and tool_name not in self.allowed_tools:
            return False, self.reason
        return True, ""


class ToolRegistry:
    """Flat tool catalog with global guards."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._tools: dict[str, tuple[ToolDefinition, str, str]] = {}
        self._guards: list[CapabilityGuard] = []

    def register(
        self,
        definition: ToolDefinition,
        plugin_id: str = "core.runtime",
        plugin_version: str = "builtin",
    ) -> Callable[[], None]:
        if not definition.name.strip():
            raise ValueError("Tool name is required")
        with self._lock:
            self._tools[definition.name] = (definition, plugin_id, plugin_version)

        def cleanup() -> None:
            with self._lock:
                self._tools.pop(definition.name, None)

        return cleanup

    def add_guard(self, guard: CapabilityGuard) -> Callable[[], None]:
        with self._lock:
            self._guards.append(guard)

        def cleanup() -> None:
            with self._lock:
                try:
                    self._guards.remove(guard)
                except ValueError:
                    pass

        return cleanup

    def get(self, name: str, agent: str) -> ToolDefinition:
        with self._lock:
            entry = self._tools.get(name)
            if not entry:
                raise KeyError(f"Unknown tool: {name}")
            definition = entry[0]
            if definition.allowed_agents and agent not in definition.allowed_agents:
                raise PermissionError(f"Agent {agent} cannot use tool {name}")
            for guard in self._guards:
                allowed, reason = guard.check(name, agent)
                if not allowed:
                    raise PermissionError(f"{reason}: {name} for {agent} ({guard.guard_id})")
            return definition

    def snapshot(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            return {
                name: {
                    "plugin_id": plugin_id,
                    "plugin_version": plugin_version,
                    "allowed_agents": sorted(defn.allowed_agents),
                }
                for name, (defn, plugin_id, plugin_version) in sorted(self._tools.items())
            }


# Keep backward-compatible alias for callers that haven't migrated yet.
ScopedToolRegistry = ToolRegistry


class EffectStack:
    """LIFO cleanup stack used by plugin installation."""

    def __init__(self) -> None:
        self._effects: list[Callable[[], None]] = []
        self._disposed = False

    def add(self, cleanup: Callable[[], None]) -> None:
        if self._disposed:
            cleanup()
            raise RuntimeError("Cannot add an effect to a disposed stack")
        self._effects.append(cleanup)

    def dispose(self) -> None:
        if self._disposed:
            return
        errors: list[Exception] = []
        for cleanup in reversed(self._effects):
            try:
                cleanup()
            except Exception as exc:  # pragma: no cover - defensive aggregation
                errors.append(exc)
        self._effects.clear()
        self._disposed = True
        if errors:
            raise RuntimeError(f"Plugin cleanup failed with {len(errors)} error(s)") from errors[0]


class PluginContext:
    def __init__(
        self,
        registry: ToolRegistry,
        manifest: PluginManifest,
        effects: EffectStack,
    ) -> None:
        self.registry = registry
        self.manifest = manifest
        self.effects = effects

    def register_tool(self, definition: ToolDefinition) -> str:
        cleanup = self.registry.register(
            definition,
            plugin_id=self.manifest.plugin_id,
            plugin_version=self.manifest.version,
        )
        self.effects.add(cleanup)
        return self.manifest.plugin_id

    def add_guard(self, guard: CapabilityGuard) -> str:
        cleanup = self.registry.add_guard(guard)
        self.effects.add(cleanup)
        return self.manifest.plugin_id


@dataclass(frozen=True, slots=True)
class ComponentSnapshot:
    snapshot_id: str
    digest: str
    scope: dict[str, Any]
    plugins: tuple[dict[str, Any], ...]
    tools: dict[str, dict[str, Any]]
    policy: dict[str, Any]
    created_at: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "digest": self.digest,
            "scope": self.scope,
            "plugins": list(self.plugins),
            "tools": self.tools,
            "policy": self.policy,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ComponentSnapshot":
        return cls(
            snapshot_id=str(value["snapshot_id"]),
            digest=str(value["digest"]),
            scope=dict(value["scope"]),
            plugins=tuple(dict(item) for item in value.get("plugins", [])),
            tools={key: dict(item) for key, item in value.get("tools", {}).items()},
            policy=dict(value.get("policy", {})),
            created_at=str(value["created_at"]),
        )


class PluginManager:
    """Simple plugin tracker — install and list. No generation management."""

    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry
        self._lock = threading.RLock()
        self._installed: dict[str, PluginManifest] = {}

    def install(
        self,
        manifest: PluginManifest,
        installer: Callable[[PluginContext], None],
        scope_key: str = "global",
        health_check: Callable[[PluginContext], bool] | None = None,
        make_active: bool = True,
    ) -> dict[str, Any]:
        effects = EffectStack()
        context = PluginContext(self.registry, manifest, effects)
        try:
            installer(context)
            if health_check is not None and not health_check(context):
                raise RuntimeError(f"Plugin health check failed: {manifest.identity}")
        except Exception:
            effects.dispose()
            raise

        with self._lock:
            self._installed[manifest.plugin_id] = manifest

        return {**manifest.as_dict(), "status": "active" if make_active else "retired"}

    def has_generation(self, plugin_id: str, version: str, scope_key: str = "global") -> bool:
        with self._lock:
            installed = self._installed.get(plugin_id)
            return installed is not None and installed.version == version

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            return [{**m.as_dict(), "status": "active"} for m in self._installed.values()]

    def snapshot(self, scope: ScopeContext, policy: dict[str, Any]) -> ComponentSnapshot:
        with self._lock:
            plugins = tuple(m.as_dict() for m in self._installed.values())
        tools = self.registry.snapshot()
        created_at = utc_now()
        payload = {
            "scope": scope.as_dict(),
            "plugins": plugins,
            "tools": tools,
            "policy": policy,
        }
        return ComponentSnapshot(
            snapshot_id=str(uuid4()),
            digest=stable_hash(payload),
            scope=scope.as_dict(),
            plugins=plugins,
            tools=tools,
            policy=policy,
            created_at=created_at,
        )
