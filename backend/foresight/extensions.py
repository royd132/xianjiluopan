from __future__ import annotations

import hashlib
import json
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Iterable
from uuid import uuid4


PLUGIN_ID = re.compile(r"[a-z0-9][a-z0-9._-]{1,79}")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _digest(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ScopeContext:
    """Capability resolution chain for one research task."""

    tenant_id: str = "default"
    preset_id: str = "global"
    task_id: str | None = None

    def chain_keys(self) -> tuple[str, ...]:
        tenant = self.tenant_id.strip().lower() or "default"
        preset = self.preset_id.strip().lower() or "global"
        keys = ["global", f"tenant:{tenant}", f"preset:{tenant}:{preset}"]
        if self.task_id:
            keys.append(f"task:{self.task_id}")
        return tuple(keys)

    def as_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "preset_id": self.preset_id,
            "task_id": self.task_id,
            "chain": list(self.chain_keys()),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ScopeContext":
        return cls(
            tenant_id=str(value.get("tenant_id", "default")),
            preset_id=str(value.get("preset_id", "global")),
            task_id=value.get("task_id"),
        )


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
        return _digest(self.as_dict(include_digest=False))

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
    """A deny is final; later guards cannot restore a rejected capability."""

    guard_id: str
    allowed_tools: frozenset[str] | None = None
    denied_tools: frozenset[str] = frozenset()
    denied_agent_tools: frozenset[tuple[str, str]] = frozenset()
    reason: str = "Capability denied by runtime policy"

    def check(self, tool_name: str, agent: str) -> tuple[bool, str]:
        if self.allowed_tools is not None and tool_name not in self.allowed_tools:
            return False, self.reason
        if tool_name in self.denied_tools or (agent, tool_name) in self.denied_agent_tools:
            return False, self.reason
        return True, ""


@dataclass(slots=True)
class _ToolRegistration:
    registration_id: str
    definition: ToolDefinition
    scope_key: str
    plugin_id: str
    plugin_version: str
    sequence: int
    active: bool


@dataclass(slots=True)
class _GuardRegistration:
    registration_id: str
    guard: CapabilityGuard
    scope_key: str
    plugin_id: str
    plugin_version: str
    sequence: int
    active: bool


@dataclass(slots=True)
class RegistrationHandle:
    registration_id: str
    activate: Callable[[], None]
    deactivate: Callable[[], None]
    cleanup: Callable[[], None]


class ScopedToolRegistry:
    """Layered tool catalog with reversible shadowing and monotonic guards."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._sequence = 0
        self._tools: dict[str, _ToolRegistration] = {}
        self._layers: dict[str, dict[str, list[str]]] = {}
        self._guards: dict[str, _GuardRegistration] = {}
        self._guard_layers: dict[str, list[str]] = {}

    def _next_sequence(self) -> int:
        self._sequence += 1
        return self._sequence

    def register_entry(
        self,
        definition: ToolDefinition,
        scope_key: str = "global",
        plugin_id: str = "core.runtime",
        plugin_version: str = "builtin",
        active: bool = True,
    ) -> RegistrationHandle:
        if not definition.name.strip():
            raise ValueError("Tool name is required")
        registration_id = str(uuid4())
        with self._lock:
            registration = _ToolRegistration(
                registration_id=registration_id,
                definition=definition,
                scope_key=scope_key,
                plugin_id=plugin_id,
                plugin_version=plugin_version,
                sequence=self._next_sequence(),
                active=active,
            )
            self._tools[registration_id] = registration
            self._layers.setdefault(scope_key, {}).setdefault(definition.name, []).append(registration_id)

        def activate() -> None:
            with self._lock:
                if registration_id in self._tools:
                    self._tools[registration_id].active = True

        def deactivate() -> None:
            with self._lock:
                if registration_id in self._tools:
                    self._tools[registration_id].active = False

        def cleanup() -> None:
            with self._lock:
                current = self._tools.pop(registration_id, None)
                if not current:
                    return
                names = self._layers.get(current.scope_key, {})
                identifiers = names.get(current.definition.name, [])
                if registration_id in identifiers:
                    identifiers.remove(registration_id)
                if not identifiers:
                    names.pop(current.definition.name, None)
                if not names:
                    self._layers.pop(current.scope_key, None)

        return RegistrationHandle(registration_id, activate, deactivate, cleanup)

    def register(
        self,
        definition: ToolDefinition,
        scope_key: str = "global",
        plugin_id: str = "core.runtime",
        plugin_version: str = "builtin",
    ) -> Callable[[], None]:
        return self.register_entry(
            definition, scope_key, plugin_id, plugin_version, active=True
        ).cleanup

    def add_guard_entry(
        self,
        guard: CapabilityGuard,
        scope_key: str = "global",
        plugin_id: str = "core.runtime",
        plugin_version: str = "builtin",
        active: bool = True,
    ) -> RegistrationHandle:
        registration_id = str(uuid4())
        with self._lock:
            registration = _GuardRegistration(
                registration_id=registration_id,
                guard=guard,
                scope_key=scope_key,
                plugin_id=plugin_id,
                plugin_version=plugin_version,
                sequence=self._next_sequence(),
                active=active,
            )
            self._guards[registration_id] = registration
            self._guard_layers.setdefault(scope_key, []).append(registration_id)

        def activate() -> None:
            with self._lock:
                if registration_id in self._guards:
                    self._guards[registration_id].active = True

        def deactivate() -> None:
            with self._lock:
                if registration_id in self._guards:
                    self._guards[registration_id].active = False

        def cleanup() -> None:
            with self._lock:
                current = self._guards.pop(registration_id, None)
                if not current:
                    return
                identifiers = self._guard_layers.get(current.scope_key, [])
                if registration_id in identifiers:
                    identifiers.remove(registration_id)
                if not identifiers:
                    self._guard_layers.pop(current.scope_key, None)

        return RegistrationHandle(registration_id, activate, deactivate, cleanup)

    def add_guard(
        self,
        guard: CapabilityGuard,
        scope_key: str = "global",
        plugin_id: str = "core.runtime",
        plugin_version: str = "builtin",
    ) -> Callable[[], None]:
        return self.add_guard_entry(
            guard, scope_key, plugin_id, plugin_version, active=True
        ).cleanup

    def _visible_registration(self, name: str, scope: ScopeContext) -> _ToolRegistration | None:
        for scope_key in reversed(scope.chain_keys()):
            identifiers = self._layers.get(scope_key, {}).get(name, [])
            registrations = [
                self._tools[item]
                for item in identifiers
                if item in self._tools and self._tools[item].active
            ]
            if registrations:
                return max(registrations, key=lambda item: item.sequence)
        return None

    def _apply_guards(self, name: str, agent: str, scope: ScopeContext) -> None:
        for scope_key in scope.chain_keys():
            identifiers = self._guard_layers.get(scope_key, [])
            guards = sorted(
                (
                    self._guards[item]
                    for item in identifiers
                    if item in self._guards and self._guards[item].active
                ),
                key=lambda item: item.sequence,
            )
            for registration in guards:
                allowed, reason = registration.guard.check(name, agent)
                if not allowed:
                    raise PermissionError(
                        f"{reason}: {name} for {agent} ({registration.guard.guard_id})"
                    )

    def get(
        self,
        name: str,
        agent: str,
        scope: ScopeContext | None = None,
        pinned_registration_id: str | None = None,
        pinned_plugin_id: str | None = None,
        pinned_plugin_version: str | None = None,
        pinned_scope_key: str | None = None,
    ) -> ToolDefinition:
        scope = scope or ScopeContext()
        with self._lock:
            if pinned_registration_id:
                registration = self._tools.get(pinned_registration_id)
                if not registration and pinned_plugin_id and pinned_plugin_version:
                    candidates = [
                        item
                        for item in self._tools.values()
                        if item.definition.name == name
                        and item.plugin_id == pinned_plugin_id
                        and item.plugin_version == pinned_plugin_version
                        and (pinned_scope_key is None or item.scope_key == pinned_scope_key)
                    ]
                    registration = max(candidates, key=lambda item: item.sequence) if candidates else None
                if not registration or registration.definition.name != name:
                    raise KeyError(f"Pinned tool registration is unavailable: {name}")
            else:
                registration = self._visible_registration(name, scope)
            if not registration:
                raise KeyError(f"Unknown tool: {name}")
            definition = registration.definition
            if definition.allowed_agents and agent not in definition.allowed_agents:
                raise PermissionError(f"Agent {agent} cannot use tool {name}")
            self._apply_guards(name, agent, scope)
            return definition

    def snapshot(self, scope: ScopeContext) -> dict[str, dict[str, Any]]:
        with self._lock:
            names = {
                name
                for scope_key in scope.chain_keys()
                for name in self._layers.get(scope_key, {})
            }
            snapshot: dict[str, dict[str, Any]] = {}
            for name in sorted(names):
                registration = self._visible_registration(name, scope)
                if not registration:
                    continue
                snapshot[name] = {
                    "registration_id": registration.registration_id,
                    "plugin_id": registration.plugin_id,
                    "plugin_version": registration.plugin_version,
                    "scope_key": registration.scope_key,
                    "allowed_agents": sorted(registration.definition.allowed_agents),
                }
            return snapshot

    def names_for(self, agent: str, scope: ScopeContext | None = None) -> list[str]:
        scope = scope or ScopeContext()
        names = []
        for name in self.snapshot(scope):
            try:
                self.get(name, agent, scope)
            except PermissionError:
                continue
            names.append(name)
        return names


class EffectStack:
    """LIFO cleanup stack used by plugin installation and rollback."""

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
        registry: ScopedToolRegistry,
        manifest: PluginManifest,
        scope_key: str,
        effects: EffectStack,
    ) -> None:
        self.registry = registry
        self.manifest = manifest
        self.scope_key = scope_key
        self.effects = effects
        self._registrations: list[RegistrationHandle] = []

    def register_tool(self, definition: ToolDefinition) -> str:
        handle = self.registry.register_entry(
            definition,
            scope_key=self.scope_key,
            plugin_id=self.manifest.plugin_id,
            plugin_version=self.manifest.version,
            active=False,
        )
        self._registrations.append(handle)
        self.effects.add(handle.cleanup)
        return handle.registration_id

    def add_guard(self, guard: CapabilityGuard) -> str:
        handle = self.registry.add_guard_entry(
            guard,
            scope_key=self.scope_key,
            plugin_id=self.manifest.plugin_id,
            plugin_version=self.manifest.version,
            active=False,
        )
        self._registrations.append(handle)
        self.effects.add(handle.cleanup)
        return handle.registration_id

    def activate(self) -> None:
        for registration in self._registrations:
            registration.activate()

    def deactivate(self) -> None:
        for registration in self._registrations:
            registration.deactivate()


@dataclass(slots=True)
class PluginHandle:
    manifest: PluginManifest
    scope_key: str
    context: PluginContext
    effects: EffectStack
    status: str = "staged"
    installed_at: str = field(default_factory=_utc_now)

    def as_dict(self) -> dict[str, Any]:
        return {
            **self.manifest.as_dict(),
            "scope_key": self.scope_key,
            "status": self.status,
            "installed_at": self.installed_at,
        }


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
    """Staged plugin activation that keeps retired generations for pinned runs."""

    def __init__(self, registry: ScopedToolRegistry) -> None:
        self.registry = registry
        self._lock = threading.RLock()
        self._handles: dict[tuple[str, str, str], PluginHandle] = {}
        self._active: dict[tuple[str, str], tuple[str, str, str]] = {}

    def install(
        self,
        manifest: PluginManifest,
        installer: Callable[[PluginContext], None],
        scope_key: str = "global",
        health_check: Callable[[PluginContext], bool] | None = None,
        make_active: bool = True,
    ) -> PluginHandle:
        identity = (scope_key, manifest.plugin_id, manifest.version)
        with self._lock:
            if identity in self._handles:
                raise ValueError(f"Plugin generation already installed: {manifest.identity} in {scope_key}")
            effects = EffectStack()
            context = PluginContext(self.registry, manifest, scope_key, effects)
            handle = PluginHandle(manifest, scope_key, context, effects)
            try:
                installer(context)
                if health_check is not None and not health_check(context):
                    raise RuntimeError(f"Plugin health check failed: {manifest.identity}")
                if make_active:
                    context.activate()
            except Exception:
                effects.dispose()
                raise

            self._handles[identity] = handle
            if make_active:
                active_key = (scope_key, manifest.plugin_id)
                previous_identity = self._active.get(active_key)
                if previous_identity:
                    previous = self._handles[previous_identity]
                    previous.context.deactivate()
                    previous.status = "retired"
                handle.status = "active"
                self._active[active_key] = identity
            else:
                handle.status = "retired"
            return handle

    def has_generation(self, plugin_id: str, version: str, scope_key: str = "global") -> bool:
        with self._lock:
            return (scope_key, plugin_id, version) in self._handles

    def rollback(self, plugin_id: str, scope_key: str = "global") -> PluginHandle:
        with self._lock:
            active_key = (scope_key, plugin_id)
            current_identity = self._active.get(active_key)
            if not current_identity:
                raise KeyError(f"No active plugin: {plugin_id} in {scope_key}")
            current = self._handles[current_identity]
            candidates = [
                (identity, handle)
                for identity, handle in self._handles.items()
                if identity[0] == scope_key
                and identity[1] == plugin_id
                and identity != current_identity
                and handle.status == "retired"
            ]
            if not candidates:
                raise ValueError(f"No retired plugin generation is available for {plugin_id}")
            previous_identity, previous = max(candidates, key=lambda item: item[1].installed_at)
            current.context.deactivate()
            current.status = "retired"
            previous.context.activate()
            previous.status = "active"
            self._active[active_key] = previous_identity
            return previous

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                handle.as_dict()
                for handle in sorted(
                    self._handles.values(),
                    key=lambda item: (item.scope_key, item.manifest.plugin_id, item.installed_at),
                )
            ]

    def _active_handles(self, scope: ScopeContext) -> list[PluginHandle]:
        selected: dict[str, PluginHandle] = {}
        for scope_key in scope.chain_keys():
            for (candidate_scope, plugin_id), identity in self._active.items():
                if candidate_scope == scope_key:
                    selected[plugin_id] = self._handles[identity]
        return sorted(selected.values(), key=lambda item: (item.scope_key, item.manifest.plugin_id))

    def snapshot(self, scope: ScopeContext, policy: dict[str, Any]) -> ComponentSnapshot:
        plugins = tuple(
            {**handle.manifest.as_dict(), "scope_key": handle.scope_key}
            for handle in self._active_handles(scope)
        )
        tools = self.registry.snapshot(scope)
        created_at = _utc_now()
        payload = {
            "scope": scope.as_dict(),
            "plugins": plugins,
            "tools": tools,
            "policy": policy,
        }
        return ComponentSnapshot(
            snapshot_id=str(uuid4()),
            digest=_digest(payload),
            scope=scope.as_dict(),
            plugins=plugins,
            tools=tools,
            policy=policy,
            created_at=created_at,
        )


def plugin_capabilities(handles: Iterable[dict[str, Any]]) -> list[str]:
    return sorted({capability for handle in handles for capability in handle.get("capabilities", [])})
