from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.app_server.backend_contract.conftest import connect_backend_contract_host
from vibe.app_server.protocol import (
    ClientCapabilities,
    RuntimeReadParams,
    SessionOptions,
)


@pytest.mark.asyncio
@pytest.mark.usefixtures("host_platform", "backend_contract_mistral_api")
async def test_oversized_agent_instructions_reach_client_diagnostics(
    tmp_path: Path,
) -> None:
    agents = tmp_path / ".vibe" / "agents"
    agents.mkdir(parents=True)
    path = agents / "reviewer.toml"
    declaration = f"instructions = {json.dumps('x' * (64 * 1024 + 1))}\n"
    path.write_text(
        'description = "Reviews a diff"\nagent_type = "subagent"\n' + declaration,
        encoding="utf-8",
    )
    connection = await connect_backend_contract_host(
        session_options=SessionOptions(cwd=str(tmp_path), trust_workspace=True),
        capabilities=ClientCapabilities(),
    )
    try:
        session = await connection.host.open_session()
        runtime = await connection.client.request(
            "runtime/read", RuntimeReadParams(session_id=session.session_id)
        )
        issues = runtime["runtime"]["issues"]
        matching = [issue for issue in issues if issue["file"] == str(path)]
        assert len(matching) == 1
        assert "instructions" in matching[0]["message"]
        assert "65536" in matching[0]["message"]
    finally:
        await connection.host.close()
