# Adapty Server-side API: custom attributes tests

Pytest suite for setting a user's custom attributes via the Adapty Server-side API v2:
`PATCH https://api.adapty.io/api/v2/server-side-api/profile/` with the `custom_attributes` field
([docs](https://adapty.io/docs/api-adapty/operations/updateProfile)). Only `custom_attributes`
is covered, other profile fields are out of scope.

## Quick start

### 1. Prerequisites

* Python 3.10 or newer (`python3 --version`)
* A free account at [app.adapty.io](https://app.adapty.io) with at least one app

### 2. Get the API key

In the Adapty dashboard open **App settings → General → API keys** and copy the **Secret key**
(starts with `secret_live_`).

> ⚠️ Use a separate Adapty app for testing: the tests create and delete real profiles.
> Never commit the key to the repository.

### 3. Clone and install

```bash
git clone https://github.com/vfomenok/adapty-custom-attributes-tests.git
cd adapty-custom-attributes-tests

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Set the key

```bash
export ADAPTY_SECRET_API_KEY="secret_live_..."           # macOS / Linux
```
```powershell
$env:ADAPTY_SECRET_API_KEY = "secret_live_..."           # Windows PowerShell
```

The variable lives only in the current terminal session; set it again in a new terminal.

### 5. Run

```bash
pytest
```

A run takes about a minute. Expected result:

```
73 passed, 6 xfailed in 64s
```

* `passed` — the API behaves as expected.
* `xfailed` — a **known API bug** (see [Findings](#findings-bugs-and-doc-gaps)); this is not a test failure.
* `failed` / `XPASS(strict)` — behaviour changed: either a regression or a known bug was fixed.

### Useful commands

| Command | What it does |
|---|---|
| `pytest -v` | Show every test by name |
| `pytest -k limit` | Run only tests whose name contains `limit` |
| `pytest tests/test_custom_attributes.py::TestKeyValidation` | Run one group of tests |
| `pytest -x` | Stop at the first failure |
| `pytest --junitxml=report.xml` | Save a JUnit report (for CI) |

### PyCharm

Open the folder as a project, select `.venv` as the interpreter, then in
**Run → Edit Configurations → pytest → Environment variables** add
`ADAPTY_SECRET_API_KEY=secret_live_...` and run the tests with the green button.

## CI (GitLab)

`.gitlab-ci.yml` runs the suite on merge requests, on the default branch, on schedules and on
manual runs ("Run pipeline"). To use it, import or mirror this repository into GitLab, then:

1. **Settings → CI/CD → Variables**: add `ADAPTY_SECRET_API_KEY` with the *Masked* and *Protected* flags.
2. Optional: **Build → Pipeline schedules**, e.g. nightly, to catch API regressions without code changes.

Results appear in the pipeline's **Tests** tab and in merge requests (JUnit report).

## Project structure

```
├── tests/
│   ├── test_custom_attributes.py   # the tests
│   └── helpers.py                  # assertions and payload builders
├── conftest.py                     # fixtures: API client, fresh profile per test
├── adapty_client.py                # thin wrapper around the Adapty API
├── pytest.ini                      # pytest settings
├── requirements.txt
└── .gitlab-ci.yml                  # GitLab CI pipeline
```

## Approach

* **Contract first, then observed behaviour.** Before writing tests the endpoint was probed manually.
  The docs define the limits (30 attributes, key ≤ 30 chars and `^[a-zA-Z0-9\-_.]+$`,
  value ≤ 50 chars, string or float) but are silent on deletion, merging, duplicates and
  error format. Tests cover both: the documented rules and the observed semantics the product
  relies on.
* **Boundary value analysis.** Every limit is tested on both sides: 30/31 attributes, 30/31-char keys,
  50/51-char values (ASCII and Cyrillic, to check that characters, not bytes, are counted).
* **Equivalence classes** for keys (each allowed char class vs. space, Unicode, punctuation)
  and value types (string, float vs. bool, object, array, integer, null).
* **State checks, not only status codes.** Write operations are verified with a follow-up
  `GET`, including that a rejected request leaves stored data untouched (atomicity).
* **Isolation.** Each test gets a fresh profile (`autotest-<uuid>`) and deletes it afterwards,
  so tests are order-independent and can be re-run.
* **Known bugs as strict `xfail`.** Defects are expressed as the expected correct behaviour and
  marked `xfail(strict=True)`. The pipeline stays green, the bug is visible in the report, and
  once the bug is fixed the test turns into XPASS and fails, reminding to remove the marker.
* **Retries only for 429/network errors.** 5xx responses are deliberately not retried, so server
  errors are not hidden.

## Coverage

| Area | Checks |
|---|---|
| Setting values | string, float (0, negative, large), numeric string stays a string, several at once, 30 at once, persistence via GET, addressing by `adapty-profile-id` |
| Key validation | 1 char, 30 chars, all allowed chars, case sensitivity; 31 chars, empty, whitespace, Cyrillic, emoji, punctuation, missing key, non-string key |
| Value validation | 50 chars (ASCII/Cyrillic), Unicode, whitespace; 51 chars, bool, object, array, integer, missing value |
| Payload | > 30 items, non-list, `null`, error points to the invalid item, invalid request is atomic |
| Update / delete | merge with existing, overwrite (incl. type change), `null` and `""` delete, unknown key with `null`, empty list, no field, duplicate keys, delete + add in one request |
| Profile limit | update when full, reuse freed slot, never more than 30 stored, error when exceeded |
| Auth / profile | invalid key, missing key, unknown, deleted and malformed profile id, no identifier |

## Findings (bugs and doc gaps)

| # | Finding | Severity | Test |
|---|---|---|---|
| 1 | When a profile already has 30 attributes, new ones are **silently dropped** with HTTP 200. Clients believe data was saved. | High | `test_exceeding_profile_limit_returns_error` (xfail) |
| 2 | Item without `value` returns **HTTP 500** (HTML page) instead of 400. | Medium | `test_missing_value_is_rejected` (xfail) |
| 3 | JSON integers (`30`) are rejected, only `30.0` is accepted. JavaScript cannot produce `30.0` (`JSON.stringify(30.0) === "30"`), so web/JS clients cannot store whole numbers. | Medium | `test_integer_value_is_accepted` (xfail) |
| 4 | Numeric key `123` is silently coerced to `"123"` instead of being rejected. | Low | `test_non_string_key_is_rejected` (xfail) |
| 5 | Missing `Authorization` header returns 403 with a plain-text body, docs promise 401 with a JSON error. | Low | `test_missing_api_key_is_rejected` |
| 6 | Undocumented: `null` and `""` delete an attribute, duplicates in one request resolve to the last value, attributes are merged rather than replaced, response order is not stable. | Doc gap | `TestUpdateAndDelete` |

## Risks and weaknesses

* **Tests run against production.** Adapty has no sandbox for the Server-side API, so the suite
  creates real profiles in a real app. Use a dedicated Adapty app for tests only. If a run is
  killed before teardown, `autotest-*` profiles remain and must be cleaned up manually.
* **Rate limits.** One run makes ~300 requests. Retries on 429 mitigate it, but parallel runs
  (`pytest-xdist`, several pipelines) can still hit the limit; CI uses `resource_group` to serialise runs.
* **Network flakiness / external dependency.** A failure may be caused by Adapty or the network,
  not by a regression. Rerun before filing a bug.
* **Pinned undocumented behaviour.** Tests for `""`-deletes, duplicate handling etc. describe
  what the API does today, not a promise. If Adapty changes it intentionally, these tests
  fail and need a product decision, not just a code fix.
* **Read-after-write.** The suite assumes `GET` immediately reflects a `PATCH` (true today). If the
  backend becomes eventually consistent, persistence checks may get flaky.
* **Secret handling.** The key grants full server-side access to the app. It must live only in
  CI variables / local env, never in the repository or logs.
* **Not covered:** concurrency (two simultaneous updates of the same profile), how attributes
  show up in the dashboard, segments and integrations; performance and load.
