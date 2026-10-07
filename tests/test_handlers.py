from bot import handlers, subscribers


def test_poll_updates_subscribes_and_moves_offset(monkeypatch):
    requested = []
    start = {"update_id": 10, "message": {"chat": {"id": 42}, "text": "/start"}}

    def fake_get_updates(offset):
        requested.append(offset)
        return [start] if offset == 0 else []

    monkeypatch.setattr(handlers, "get_updates", fake_get_updates)
    monkeypatch.setattr(handlers, "send_message", lambda *args, **kwargs: None)

    handlers.poll_updates()
    handlers.poll_updates()  # второй опрос должен просить апдейты уже после 10-го

    assert requested == [0, 11]
    assert 42 in subscribers.load_subscribers()
