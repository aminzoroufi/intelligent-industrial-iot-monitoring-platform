# Continuous integration and dependency policy

The CI workflow has four independent gates: Python/contracts/docs/hardware,
dashboard, shared firmware host tests, and the full Compose/browser path. The
security workflow audits both lock files, validates the committed license
inventory, and scans complete Git history with a checksum-pinned Gitleaks
binary. Neither workflow needs private credentials or physical hardware.

Every `uses:` reference is pinned to a full Git commit. The selected releases
were checked against their official GitHub release pages on 2026-08-12:

- `actions/checkout` 7.0.1;
- `actions/setup-python` 7.0.0;
- `actions/setup-node` 7.0.0;
- `actions/upload-artifact` 7.0.1.

Dependabot proposes action updates monthly. A maintainer must read the upstream
release notes, review permission/runtime changes, replace the full SHA and
version comment together, and let all gates pass. Floating major tags are not
accepted.

Python dependency changes require an exact pin in `requirements/runtime.lock`
or `requirements/ci.lock` and a reviewed row in
`requirements/python-license-policy.csv`. The CI lock includes the runtime lock
and fully pins its additional development/documentation graph. JavaScript
changes must be made through `package-lock.json`. Refresh the public inventory
with:

```bash
.venv/bin/python scripts/check_dependency_licenses.py --write
```

The policy rejects absent/unknown licenses and strong-copyleft expressions that
have not received an explicit licensing decision. `reviewed` rows are not legal
advice; they record the engineering distribution decision and preservation
obligations. The project license does not replace any dependency license.

CI compiles only the hardware-independent C core. ESP-IDF, STM32Cube/ARM, KiCad
ERC/DRC, FreeCAD execution, bench tests, and field tests remain separate named
gates and must never be inferred from a green hosted workflow.
