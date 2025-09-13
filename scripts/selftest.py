from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
PY = shutil.which("python3") or sys.executable


def run(cmd: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> tuple[int, str, str]:
    p = subprocess.run(cmd, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return p.returncode, p.stdout, p.stderr


def clean_output(s: str) -> str:
    # Drop Homebrew/pyenv noise lines at top, keep diagnose body
    lines = [ln for ln in s.splitlines() if not ln.startswith('/opt/homebrew/') and 'pyenv:' not in ln]
    return '\n'.join(lines)


def expect_contains(name: str, haystack: str, needle: str) -> None:
    if needle not in haystack:
        raise AssertionError(f"[{name}] Missing expected text: {needle}\n--- output ---\n{haystack}\n--------------")


def test_repo_config() -> None:
    code, out, err = run([PY, str(REPO_ROOT / 'chatmock.py'), 'diagnose'])
    out = clean_output(out)
    assert code == 0, f"diagnose failed: {err or out}"
    expect_contains('repo-config', out, 'Config diagnose')
    expect_contains('repo-config', out, 'Server: http://')
    expect_contains('repo-config', out, 'Instructions file:')
    expect_contains('repo-config', out, 'prompt.md')


def test_explicit_config() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / 'my-prompt.md').write_text('SELFTEST_PROMPT_123', encoding='utf-8')
        (d / 'cfg.yaml').write_text(
            '\n'.join([
                'server:',
                '  host: 0.0.0.0',
                '  port: 8044',
                'reasoning:',
                '  effort: low',
                '  summary: none',
                '  compat: legacy',
                'login:',
                '  bind_host: 0.0.0.0',
                'oauth:',
                '  client_id: app_SELFTEST',
                'upstream:',
                '  responses_url: https://example.invalid/responses',
                'instructions:',
                '  path: ./my-prompt.md',
            ]),
            encoding='utf-8',
        )
        code, out, err = run([PY, str(REPO_ROOT / 'chatmock.py'), 'diagnose', '--config', str(d / 'cfg.yaml')], cwd=d)
        out = clean_output(out)
        assert code == 0, f"diagnose explicit failed: {err or out}"
        expect_contains('explicit-config', out, 'Server: http://0.0.0.0:8044')
        expect_contains('explicit-config', out, 'effort=low')
        expect_contains('explicit-config', out, 'summary=none')
        expect_contains('explicit-config', out, 'compat=legacy')
        expect_contains('explicit-config', out, 'Login bind host: 0.0.0.0')
        expect_contains('explicit-config', out, 'OAuth client id: app_SELFTEST')
        expect_contains('explicit-config', out, 'Upstream Responses URL: https://example.invalid/responses')
        expect_contains('explicit-config', out, "Instructions file:")
        expect_contains('explicit-config', out, "my-prompt.md")


def test_no_pwd_config() -> None:
    # Ensure PWD config is not picked up implicitly
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / 'config.yaml').write_text('\n'.join(['server:', '  host: 127.0.0.1', '  port: 8099']), encoding='utf-8')
        env = os.environ.copy()
        env['PYTHONPATH'] = str(REPO_ROOT)
        code, out, err = run([PY, '-m', 'chatmock.cli', 'diagnose'], cwd=d, env=env)
        out = clean_output(out)
        assert code == 0, f"diagnose failed: {err or out}"
        # Should show default 127.0.0.1:8000 since PWD config is ignored
        expect_contains('no-pwd-config', out, 'Server: http://127.0.0.1:8000')


def main() -> None:
    tests = [
        ('repo-config', test_repo_config),
        ('explicit-config', test_explicit_config),
        ('no-pwd-config', test_no_pwd_config),
    ]
    failures = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS {name}")
        except Exception as e:
            failures += 1
            print(f"FAIL {name}: {e}")
    if failures:
        sys.exit(1)
    print('All self-tests passed')


if __name__ == '__main__':
    main()
