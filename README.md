[![Codecov (with branch)](https://img.shields.io/codecov/c/github/jaysphoto/ha-ingenium/dev)](https://app.codecov.io/gh/jaysphoto/ha-ingenium/tree/dev)
[![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/jaysphoto/ha-ingenium/tests.yml)](https://github.com/jaysphoto/ha-ingenium/actions)


# Ingenium Home Assistant custom integration

This workspace contains a minimal scaffold for a Home Assistant custom integration named "Ingenium".

Install locally by copying the `custom_components/ingenium` folder into your Home Assistant `config/custom_components` directory.

Development & testing

- Create a virtual environment and install dev requirements:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements_dev.txt
```

- Run tests:

```bash
pytest
```

Files added:
- `custom_components/ingenium/` - integration boilerplate
- `tests/` - minimal test using `pytest-homeassistant-custom-component`
