import pytest

# Override the parent conftest's clean_database fixture
# Parser tests don't need database access
@pytest.fixture(autouse=True)
def clean_database():
    """No-op database fixture for parser tests"""
    yield
