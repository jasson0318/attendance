"""Pages base path / API_BASE / SW 不 cache API。"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"


def test_config_has_base_path_and_api_base():
    cfg = (FRONTEND / "static" / "js" / "config.js").read_text(encoding="utf-8")
    assert "API_BASE" in cfg
    assert "BASE_PATH" in cfg
    assert "apiUrl" in cfg
    assert "adminUrl" in cfg
    assert "127.0.0.1" not in cfg
    assert "localhost" not in cfg
    assert ":8800" not in cfg


def test_service_worker_skips_api_cache():
    sw = (FRONTEND / "sw.js").read_text(encoding="utf-8")
    assert "isApiRequest" in sw
    assert "/api/" in sw
    assert "network-only" in sw or "不" in sw  # 註解標明不寫 cache
    # fetch handler returns early for API（不 respondWith cache）
    assert "if (isApiRequest(url))" in sw


def test_manifest_relative_scope():
    manifest = (FRONTEND / "manifest.webmanifest").read_text(encoding="utf-8")
    assert '"scope": "./"' in manifest or '"scope":"./"' in manifest
    assert "start_url" in manifest


def test_html_uses_relative_assets():
    for name in ("index.html", "admin.html"):
        html = (FRONTEND / name).read_text(encoding="utf-8")
        assert 'href="/static/' not in html
        assert 'src="/static/' not in html
        assert "static/js/config.js" in html


def test_prepare_pages_script_exists():
    assert (ROOT / "scripts" / "prepare_github_pages.py").exists()
    assert (ROOT / ".github" / "workflows" / "deploy-pages.yml").exists()


def test_prepare_api_base_requires_https():
    import importlib.util

    import pytest

    path = ROOT / "scripts" / "prepare_github_pages.py"
    spec = importlib.util.spec_from_file_location("prepare_github_pages", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    assert mod.normalize_api_base("") == ""
    assert mod.normalize_api_base("https://example.ngrok-free.app/") == "https://example.ngrok-free.app"
    with pytest.raises(SystemExit):
        mod.normalize_api_base("http://example.ngrok-free.app")
    with pytest.raises(SystemExit):
        mod.normalize_api_base("https://<NGROK_PUBLIC_DOMAIN>")


def test_production_disables_openapi_docs():
    text = (ROOT / "backend" / "app" / "main.py").read_text(encoding="utf-8")
    assert 'docs_url=None if _is_production else "/docs"' in text
    assert 'openapi_url=None if _is_production else "/openapi.json"' in text


def test_runtime_config_alias_supported():
    cfg = (FRONTEND / "static" / "js" / "config.js").read_text(encoding="utf-8")
    assert "ATTENDANCE_CONFIG" in cfg
    wf = (ROOT / ".github" / "workflows" / "deploy-pages.yml").read_text(encoding="utf-8")
    assert "ATTENDANCE_API_BASE" in wf


def test_health_endpoint():
    from fastapi.testclient import TestClient
    from backend.app.main import app

    c = TestClient(app)
    r = c.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "ok"
    assert "DATABASE_URL" not in str(body)
    assert "SECRET_KEY" not in str(body)
    assert c.get("/docs").status_code == 200
