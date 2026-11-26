# Contributing

Thank you for contributing examples, review cases, and implementation improvements.

## Good contributions

- a minimal reproducible plan-cache case
- a false-reuse or missed-invalidation example
- a synthetic Agent Card evolution case
- a test for demand evidence or current-request rebinding
- an evaluation protocol with independent labels
- documentation that clarifies the difference between observation and semantic compatibility

## Before opening a pull request

```bash
pip install -e '.[test]'
pytest -q
python3 examples/run_demo.py
python3 examples/lifecycle_demo.py
python3 examples/generation_race.py
```

Keep examples synthetic. Do not include credentials, personal data, production URLs, private Agent Cards, or raw business execution results.

Please describe the behavior that changes, the evidence supporting it, and any uncertainty that remains. This project treats `unknown` as a meaningful result rather than silently converting it to compatible.
