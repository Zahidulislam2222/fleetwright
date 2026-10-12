"""Workflow activity must remain readable through the existing console audit API."""

import pytest
from test_workflows import proposal

from apikit import Api

pytestmark = pytest.mark.integration


async def test_workflow_events_fit_owner_and_public_audit_response(api: Api) -> None:
    _access, job, _actor, _token = await proposal(api)
    owner = await api.signed_in("owner")
    public = api.client()
    try:
        for client in (owner, public):
            response = await client.get("/v1/audit", params={"limit": 100})
            assert response.status_code == 200
            rows = response.json()["items"]
            assert any(row["role"] == "workflow" and row["action"] == "submitted" for row in rows)
        assert any(
            row["target"] == job["id"] for row in (await owner.get("/v1/audit", params={"limit": 100})).json()["items"]
        )
    finally:
        await owner.aclose()
        await public.aclose()
