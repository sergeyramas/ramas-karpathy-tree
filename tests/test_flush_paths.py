from scripts.flush import append_to_daily_log_for_slug


def test_creates_per_slug_subdir(tmp_path, monkeypatch):
    daily_dir = tmp_path / "daily"
    monkeypatch.setattr("scripts.flush.DAILY_DIR", daily_dir)

    append_to_daily_log_for_slug(
        slug="betaline",
        content="Решение: использовать Postgres",
        section="Session",
        date_iso="2026-05-01",
    )

    log = daily_dir / "betaline" / "2026-05-01.md"
    assert log.exists()
    body = log.read_text()
    assert "Решение: использовать Postgres" in body
    assert "## Sessions" in body


def test_appends_to_existing(tmp_path, monkeypatch):
    daily_dir = tmp_path / "daily"
    monkeypatch.setattr("scripts.flush.DAILY_DIR", daily_dir)

    append_to_daily_log_for_slug(slug="ebay", content="первое", date_iso="2026-05-01")
    append_to_daily_log_for_slug(slug="ebay", content="второе", date_iso="2026-05-01")

    log = daily_dir / "ebay" / "2026-05-01.md"
    body = log.read_text()
    assert "первое" in body
    assert "второе" in body


def test_global_slug_works(tmp_path, monkeypatch):
    daily_dir = tmp_path / "daily"
    monkeypatch.setattr("scripts.flush.DAILY_DIR", daily_dir)

    append_to_daily_log_for_slug(slug="_global", content="вне проекта", date_iso="2026-05-01")
    assert (daily_dir / "_global" / "2026-05-01.md").exists()
