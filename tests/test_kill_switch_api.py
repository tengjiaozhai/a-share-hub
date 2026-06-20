"""Kill Switch API 测试：actor_user_id 归属验证"""

from src.storage.system_runtime_store import SystemRuntimeStore


def test_kill_switch_event_records_authenticated_actor(authenticated_admin_client, system_store):
    """激活 kill switch 的事件必须记录调用者 actor_user_id。"""
    response = authenticated_admin_client.post(
        "/api/v1/kill-switch/activate",
        json={"reason": "manual halt"},
    )
    assert response.status_code == 200, response.text
    event = system_store.list_kill_switch_events(limit=1)[0]
    assert event["actor_user_id"] == "test-user"


def test_kill_switch_deactivate_records_authenticated_actor(authenticated_admin_client, system_store):
    """停用 kill switch 的事件必须记录调用者 actor_user_id。"""
    response = authenticated_admin_client.post(
        "/api/v1/kill-switch/deactivate",
        json={"reason": "resume trading"},
    )
    assert response.status_code == 200, response.text
    event = system_store.list_kill_switch_events(limit=1)[0]
    assert event["actor_user_id"] == "test-user"
    assert event["active"] is False


def test_kill_switch_status_remains_queryable_after_event(authenticated_admin_client, system_store):
    """多个事件后，list_kill_switch_events 必须包含每个 actor 的归属。"""
    authenticated_admin_client.post("/api/v1/kill-switch/activate", json={"reason": "first"})
    authenticated_admin_client.post("/api/v1/kill-switch/deactivate", json={"reason": "second"})

    events = system_store.list_kill_switch_events(limit=10)
    assert len(events) >= 2
    for event in events:
        assert event["actor_user_id"] == "test-user"
