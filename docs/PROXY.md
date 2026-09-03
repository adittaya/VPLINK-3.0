# Proxy (optional)

The template runs direct by default. The proxy layer is opt-in and reuses
the existing project's proxy technology in generic form:

- **rotation** avoiding proxies used in the last 24h
- **blacklist** with 24h TTL (`Blacklist` in `src/proxy.py`)
- **fast CONNECT liveness check** (`tcp_check`, Engine 1 from `legacy/proxy_rotator.py`)
- **Supabase pool source** (same table/query pattern as `legacy/proxy_rotator.py`,
  but with env-driven host/key/table — no hardcoded defaults)

## Providers

| Provider | Source | Use when |
| -------- | ------ | -------- |
| `EnvProxyProvider` | `PROXY_URL` / `HTTP_PROXY` / `HTTPS_PROXY` | one static proxy |
| `FileProxyProvider` | `PROXY_FILE` text file, one URL/line | small rotating pool, no backend |
| `SupabaseProxyProvider` | `SUPABASE_URL` + key, `PROXY_TABLE` | large shared pool (legacy tech) |

All implement:

```python
class ProxyProvider(Protocol):
    def get_proxy(self) -> str | None: ...
    def mark_dead(self, proxy: str) -> None: ...
```

## Resolution order

`src/proxy.py::get_provider(cfg)` returns:

1. `None` when disabled (`PROXY_ENABLED` unset/false and no proxy details present)
2. `SupabaseProxyProvider` when `SUPABASE_URL` + key are set
3. `FileProxyProvider` when `PROXY_FILE` exists
4. `EnvProxyProvider` when a proxy URL env var is set
5. `None` otherwise (direct connection)

`src/browser.py` calls `get_proxy_url(cfg)` automatically, and
`examples/with_proxy.py` shows explicit handling (logging + `mark_dead` hook).

## Examples

```bash
cp proxies.example.txt proxies.txt   # add your entries (git-ignored)

# static:
PROXY_ENABLED=true PROXY_URL=http://user:pass@host:port python3 examples/with_proxy.py

# file pool:
PROXY_ENABLED=true PROXY_FILE=proxies.txt python3 examples/with_proxy.py

# Supabase pool (needs `requests`, already in requirements.txt):
PROXY_ENABLED=true SUPABASE_URL=https://xyz.supabase.co SUPABASE_KEY=... \
  PROXY_TABLE=proxy_results PROXY_TIER=premium \
  python3 examples/with_proxy.py
```

## Custom pool

Implement the two-method `ProxyProvider` protocol and return it from your
own factory. Keep `mark_dead()` semantics: blacklist immediately, and
remove/report upstream on a best-effort basis (see
`SupabaseProxyProvider.mark_dead`).

## Legacy mapping

| Legacy (`legacy/…`) | Template equivalent |
| ------ | ------------------- |
| `proxy_rotator.py::fetch_proxies/get_proxy` | `SupabaseProxyProvider._fetch/get_proxy` |
| `proxy_rotator.py::mark_dead/delete_proxy` | `SupabaseProxyProvider.mark_dead` |
| `proxy_rotator.py::_try_connect_quick/test_proxy_quick` | `tcp_check` |
| `config.load_proxy_history/save_proxy_history` rotation | in-memory 24h history in `File/SupabaseProxyProvider` |
| `config.load_proxy_blacklist` 24h TTL | `Blacklist` class |
| `test_proxy_selenium` (Engine 2) | not bundled — validate via your real flow instead |
