poetry install
poetry build
pipx uninstall rustsmith_validator
pipx install dist/rustsmith_validator-0.1.0-py3-none-any.whl --force