from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("mistralai_vibe_local_harness.vibe")

from mistralai_vibe_local_harness.protocol import (
    RustHookCompletedEvent,
    RustHookSkip,
    RustHookToolCall,
    RustPostToolCallHookAction,
    RustPostToolCallHookInput,
    RustPostToolCallHookResult,
    RustPreToolCallHookAction,
    RustPreToolCallHookInput,
    RustPreToolCallHookResult,
    RustRuntimeBuiltinToolCall,
    RustTextContentBlock,
    RustToolSuccessResult,
)
from mistralai_vibe_local_harness.session_protocol import SessionStartParams
from mistralai_vibe_local_harness.vibe._hook_config import (
    ForeignHookDefinition,
    compile_foreign_hooks,
)
from mistralai_vibe_local_harness.vibe._host import (
    UnifiedHarnessSessionBackendHost,
    _core_config,
)
from mistralai_vibe_local_harness.vibe._runtime_config import LocalRuntimeAdapterConfig
from mistralai_vibe_local_harness.vibe._subagents._configuration import (
    resolve_declared_agent_types,
)
from mistralai_vibe_local_harness.vibe._subagents._models import (
    DeclaredAgentTypeProfile,
    SubagentSessionIdentity,
)


@pytest.mark.asyncio
@pytest.mark.parametrize("agent_type", [None, "reviewer"])
@pytest.mark.parametrize("point", ["pre_tool", "post_tool"])
@pytest.mark.parametrize("restore", [False, True])
async def test_child_hook_identity_survives_creation_and_restore(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    agent_type: str | None,
    point: str,
    restore: bool,
) -> None:
    payloads: list[tuple[str, dict[str, Any]]] = []

    async def capture(
        command: str, _config: LocalRuntimeAdapterConfig, _timeout: float, stdin: bytes
    ) -> str:
        payloads.append((command, json.loads(stdin)))
        return json.dumps({"decision": "deny", "reason": command})

    monkeypatch.setattr(
        "mistralai_vibe_local_harness.vibe._foreign_hooks._run_command", capture
    )
    root_config = _core_config("root")
    adapter = LocalRuntimeAdapterConfig.at(
        cwd=tmp_path, roots=(tmp_path,), process_authority="disabled"
    )
    host = UnifiedHarnessSessionBackendHost(tmp_path / "sessions")
    host.configure_runtime(root_config, adapter)
    configured = host._resolve_subagents(root_config, adapter)
    configured = resolve_declared_agent_types(
        configured,
        adapter,
        [
            DeclaredAgentTypeProfile(
                agent_type="reviewer",
                description="Reviews changes",
                profile_path=str(tmp_path / "reviewer.toml"),
                authority_digest="reviewer",
            )
        ],
    )
    parents = []
    try:
        for name in ("first", "second"):
            hooks = compile_foreign_hooks([
                ForeignHookDefinition(name="guard", point=point, command=name)
            ])
            parent = await host.start(
                SessionStartParams(history_limit=1),
                hook_bindings=hooks.bindings,
                hook_handlers=hooks.handlers,
            )
            parents.append((name, parent))

        for index, (name, parent) in enumerate(parents):
            child_id = f"child-{index}"
            identity = SubagentSessionIdentity(
                session_id=child_id,
                root_session_id=parent.session_id,
                parent_session_id=parent.session_id,
            )
            binding = configured.bindings[agent_type]
            handle = await host.create_or_restore_child(
                identity=identity,
                binding=binding,
                spawn_key=name,
                start_new_actions=False,
                require_existing=False,
            )
            if restore:
                await host.unload_child(handle)
                handle = await host.create_or_restore_child(
                    identity=identity,
                    binding=binding,
                    spawn_key=name,
                    start_new_actions=False,
                    require_existing=True,
                )
            child = host._require_live_child(handle)
            state = child._action_adapter
            assert state is not None
            call = RustHookToolCall(
                action_id="tool-action",
                call_id="tool-call",
                call=RustRuntimeBuiltinToolCall(
                    name="file_system.bash", arguments={"command": "guarded"}
                ),
            )
            hook_ids = [
                hook.id
                for hook in child._runtime_for_host().config.capabilities.hook_bindings
            ]
            if point == "pre_tool":
                action = RustPreToolCallHookAction(
                    action_id="hook-action",
                    turn_id="turn",
                    hook_binding_ids=hook_ids,
                    input=RustPreToolCallHookInput(tool_call=call),
                )
            else:
                action = RustPostToolCallHookAction(
                    action_id="hook-action",
                    turn_id="turn",
                    hook_binding_ids=hook_ids,
                    input=RustPostToolCallHookInput(
                        tool_call=call,
                        tool_result=RustToolSuccessResult(
                            content=[RustTextContentBlock(text="original")]
                        ),
                    ),
                )
            event = await state.execute(action)
            assert isinstance(event, RustHookCompletedEvent)
            if point == "pre_tool":
                assert isinstance(event.result, RustPreToolCallHookResult)
                assert isinstance(event.result.output, RustHookSkip)
                blocks = event.result.output.reason
            else:
                assert isinstance(event.result, RustPostToolCallHookResult)
                blocks = event.result.output.tool_result.content
            assert blocks
            assert isinstance(blocks[0], RustTextContentBlock)
            assert blocks[0].text == name
            command, payload = payloads[-1]
            assert command == name
            assert payload["hook_event_name"] == point
            assert payload["session_id"] == child_id
            assert payload["parent_session_id"] == parent.session_id
            assert payload["agent_type"] == agent_type
            assert payload["transcript_path"] == str(
                tmp_path / "sessions" / "unified" / child_id
            )
    finally:
        await host.shutdown()
