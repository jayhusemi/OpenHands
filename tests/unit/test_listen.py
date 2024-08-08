from unittest.mock import patch
from opendevin.core.config import AppConfig


# Mock the SessionManager to avoid asyncio issues
class MockSessionManager:
    def __init__(self, *args, **kwargs):
        pass


# Mock StaticFiles
class MockStaticFiles:
    def __init__(self, *args, **kwargs):
        pass


# Patch necessary components before importing from listen
with patch('opendevin.server.session.SessionManager', MockSessionManager), patch(
    'fastapi.staticfiles.StaticFiles', MockStaticFiles
):
    from opendevin.server.listen import load_file_upload_config


def test_load_file_upload_config():
    config = AppConfig(
        file_uploads_max_file_size_mb=10,
        file_uploads_restrict_file_types=True,
        file_uploads_allowed_extensions=['.txt', '.pdf'],
    )
    with patch('opendevin.server.listen.config', config):
        max_size, restrict_types, allowed_extensions = load_file_upload_config()

        assert max_size == 10
        assert restrict_types is True
        assert set(allowed_extensions) == {'.txt', '.pdf'}


def test_load_file_upload_config_invalid_max_size():
    config = AppConfig(
        file_uploads_max_file_size_mb=-5,
        file_uploads_restrict_file_types=False,
        file_uploads_allowed_extensions=[],
    )
    with patch('opendevin.server.listen.config', config):

        max_size, restrict_types, allowed_extensions = load_file_upload_config()

        assert max_size == 0  # Should default to 0 when invalid
        assert restrict_types is False
        assert allowed_extensions == ['.*']  # Should default to '.*' when empty
