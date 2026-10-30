from pathlib import Path


def test_live_event_migration_makes_source_links_nullable():
    migration = Path(__file__).parents[1] / "alembic" / "versions" / "7c91a6d8e2f4_live_camera_events.py"
    content = migration.read_text(encoding="utf-8")
    assert '"video_id"' in content and '"job_id"' in content
    assert "nullable=True" in content
