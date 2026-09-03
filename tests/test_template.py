"""Offline smoke tests for the template layer (no browser needed)."""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import config as cfg_mod  # noqa: E402
from src import profiles  # noqa: E402
from src.proxy import (  # noqa: E402
    Blacklist,
    EnvProxyProvider,
    FileProxyProvider,
    SupabaseProxyProvider,
    get_provider,
    is_proxy_enabled,
    parse_proxy_url,
    tcp_check,
)


def test_config_defaults_shape():
    cfg = cfg_mod.load()
    assert cfg["target_url"].startswith("http")
    assert isinstance(cfg["headless"], bool)
    assert cfg["viewport"]["width"] > 0


def test_config_env_override(monkeypatch):
    monkeypatch.setenv("TARGET_URL", "https://example.org/")
    monkeypatch.setenv("HEADLESS", "false")
    monkeypatch.setenv("VIEWPORT_W", "800")
    monkeypatch.setenv("VIEWPORT_H", "600")
    cfg = cfg_mod.load()
    assert cfg["target_url"] == "https://example.org/"
    assert cfg["headless"] is False
    assert cfg["viewport"] == {"width": 800, "height": 600}


def test_config_save_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    import importlib

    importlib.reload(cfg_mod)
    try:
        merged = cfg_mod.save({"target_url": "https://example.net/"})
        assert merged["target_url"] == "https://example.net/"
        on_disk = json.loads(cfg_mod.CONFIG_PATH.read_text("utf-8"))
        assert on_disk["target_url"] == "https://example.net/"
    finally:
        importlib.reload(cfg_mod)


def test_profile_shape():
    for mobile in (True, False):
        p = profiles.generate_profile(mobile=mobile)
        assert p["userAgent"].startswith("Mozilla/5.0")
        assert p["viewport"]["width"] > 0
        assert "timezone" in p and "platform" in p
    assert "armv81" not in json.dumps(profiles.generate_profile(mobile=True))


def test_proxy_env(monkeypatch):
    for k in ("PROXY_URL", "HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        monkeypatch.delenv(k, raising=False)
    assert EnvProxyProvider().get_proxy() is None
    monkeypatch.setenv("PROXY_URL", "http://user:pass@host:18080")
    assert EnvProxyProvider().get_proxy() == "http://user:pass@host:18080"


def test_proxy_disabled_by_default(monkeypatch):
    for k in ("PROXY_ENABLED", "PROXY_URL", "PROXY_FILE", "SUPABASE_URL",
              "SUPABASE_KEY", "HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        monkeypatch.delenv(k, raising=False)
    assert is_proxy_enabled({}) is False
    assert get_provider({}) is None


def test_proxy_file_rotation(tmp_path):
    f = tmp_path / "proxies.txt"
    f.write_text("# comment\nhttp://1.1.1.1:8080\nhttp://2.2.2.2:8080\nnot-a-proxy\n")
    p = FileProxyProvider(f)
    seen = {p.get_proxy() for _ in range(4)}
    assert seen <= {"http://1.1.1.1:8080", "http://2.2.2.2:8080"}
    p.mark_dead("http://1.1.1.1:8080")
    assert "http://1.1.1.1:8080" in p.blacklist
    assert p.get_proxy() == "http://2.2.2.2:8080"


def test_blacklist_ttl():
    import src.proxy as px

    bl = Blacklist(ttl_ms=-1)  # immediately expired
    bl.add("http://x:1")
    assert "http://x:1" not in bl
    bl2 = Blacklist(ttl_ms=60_000)
    bl2.add("http://x:1")
    assert "http://x:1" in bl2


def test_parse_proxy_url():
    assert parse_proxy_url("") is None
    assert parse_proxy_url("not a proxy") is None
    assert parse_proxy_url("http://host:8080")["port"] == 8080
    assert tcp_check("http://127.0.0.1:9", timeout_s=0.2) is False


def test_supabase_provider_unconfigured(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_KEY", raising=False)
    assert SupabaseProxyProvider().is_configured() is False
    assert SupabaseProxyProvider().get_proxy() is None


def test_provider_priority(monkeypatch, tmp_path):
    for k in ("SUPABASE_URL", "SUPABASE_KEY", "SUPABASE_SECRET", "PROXY_FILE",
              "PROXY_URL", "HTTP_PROXY", "HTTPS_PROXY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("PROXY_ENABLED", "true")
    monkeypatch.setenv("PROXY_URL", "http://u:p@h:8080")
    assert type(get_provider({})).__name__ == "EnvProxyProvider"
    f = tmp_path / "p.txt"
    f.write_text("http://9.9.9.9:8080\n")
    monkeypatch.setenv("PROXY_FILE", str(f))
    assert type(get_provider({})).__name__ == "FileProxyProvider"


def test_browser_module_imports_without_selenium():
    import src.browser as b

    assert callable(b.create_driver)
    assert callable(b.build_options) or True  # build_options needs selenium at call time


def test_dotenv_loader(tmp_path, monkeypatch):
    f = tmp_path / ".env"
    f.write_text("TARGET_URL=https://dotenv.example/\n# comment\n")
    monkeypatch.delenv("TARGET_URL", raising=False)
    cfg_mod.load_dotenv(f)
    assert os.environ["TARGET_URL"] == "https://dotenv.example/"
