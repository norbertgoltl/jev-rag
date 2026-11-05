from pathlib import Path
from typing import Any, cast

from jev_rag_api.core.config import Settings


def build_settings(_env_file: Path | None = None, **values: Any) -> Settings:
    """Build Settings without reading any dotenv file.

    ``_env_file`` is a pydantic-settings init option that static typing does not model,
    so the untyped call is isolated here instead of repeated across the test suite.
    """
    settings: Settings = cast(Any, Settings)(_env_file=_env_file, **values)
    return settings
