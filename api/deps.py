"""Shared dependencies for the Snow-Town visualization API.

Provides singleton instances of ContractStore, AcademyReader, and UMReader
configured via environment variables with sensible defaults for the EC2 layout.
"""

import os
from pathlib import Path

from contracts.store import ContractStore

from api.readers.academy_reader import AcademyReader
from api.readers.um_reader import UMReader

# Configurable paths with defaults matching EC2 layout
ST_RECORDS_DATA_DIR = Path(os.environ.get(
    "ST_RECORDS_DATA_DIR",
    str(Path.home() / "projects" / "st-records" / "data"),
))

ACADEMY_PERSONAS_DIR = Path(os.environ.get(
    "ACADEMY_PERSONAS_DIR",
    str(Path.home() / "projects" / "st-agent-registry" / "personas"),
))

UM_DB_PATH = Path(os.environ.get(
    "UM_DB_PATH",
    str(Path.home() / "incoming" / "caught_ideas.db"),
))

# Singletons — initialized once, shared across request handlers
_store: ContractStore | None = None
_academy: AcademyReader | None = None
_um: UMReader | None = None


def get_store() -> ContractStore:
    global _store
    if _store is None:
        _store = ContractStore(data_dir=ST_RECORDS_DATA_DIR)
    return _store


def get_academy() -> AcademyReader:
    global _academy
    if _academy is None:
        _academy = AcademyReader(personas_dir=ACADEMY_PERSONAS_DIR)
    return _academy


def get_um() -> UMReader:
    global _um
    if _um is None:
        _um = UMReader(db_path=UM_DB_PATH)
    return _um


def shutdown() -> None:
    """Clean up resources on shutdown."""
    global _store, _academy, _um
    if _store is not None:
        _store.close()
        _store = None
    _academy = None
    _um = None
