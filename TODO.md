# TODO

## Current Status

The project has been modernized with the following improvements:

✅ **Completed:**
- Python project structure with `pyproject.toml`
- Dependency management via `uv`
- CLI migration from `argparse` to `Typer`
- Code formatting with `black`
- Linting with `ruff`
- Testing infrastructure with `pytest`
- `Makefile` with quality check commands
- Updated documentation

## Future Improvements

### Type Hints
- [ ] Add comprehensive type hints to all functions
- [ ] Achieve full `mypy --strict` compliance
- [ ] Current blocker: Legacy code has many type issues requiring extensive refactoring

### Testing
- [ ] Increase test coverage
- [ ] Add integration tests for end-to-end workflows
- [ ] Add tests for Parquet file handling
- [ ] Add tests for edge cases (empty files, malformed data, etc.)

### Documentation
- [ ] Add docstring examples for key functions
- [ ] Create user guide with detailed examples
- [ ] Document data format requirements
- [ ] Add troubleshooting section

### Code Quality
- [ ] Refactor large functions into smaller, testable units
- [ ] Reduce complexity in core anonymization logic
- [ ] Add more descriptive variable names in complex sections
- [ ] Consider splitting large modules into smaller ones

### Features
- [ ] Add progress indicators for large CVR files
- [ ] Add validation mode to check CVR format before processing
- [ ] Support additional output formats
- [ ] Add configuration file support
- [ ] Improve error messages with actionable suggestions

### CI/CD
- [ ] Set up GitHub Actions workflow
- [ ] Run tests on multiple Python versions (3.12+)
- [ ] Automated code quality checks on PRs
- [ ] Automated documentation generation
