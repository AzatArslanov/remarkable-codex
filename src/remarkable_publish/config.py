from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import tomllib


@dataclass(frozen=True, slots=True)
class Settings:
    artifact_directory: Path = Path("artifacts")
    artifact_host_directory: Path | None = None
    state_directory: Path = Path(".remarkable-state")
    import_roots: tuple[Path, ...] = ()
    import_host_roots: tuple[Path, ...] = ()


def load_settings(path: Path | None) -> Settings:
    data: dict = {}
    if path is not None and path.exists():
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    publish = data.get("publish", {})
    if not isinstance(publish, dict):
        raise ValueError("[publish] must be a TOML table")
    removed_options = {"backend", "experimental_simple_upload"}.intersection(publish)
    if removed_options:
        names = ", ".join(sorted(removed_options))
        raise ValueError(f"removed publish option: {names}; uploads always publish")
    raw_import_roots = publish.get("import_roots", [])
    if not isinstance(raw_import_roots, list) or not all(isinstance(item, str) for item in raw_import_roots):
        raise ValueError("publish.import_roots must be an array of paths")
    base = Settings(
        artifact_directory=Path(str(publish.get("artifact_directory", "artifacts"))),
        state_directory=Path(str(publish.get("state_directory", ".remarkable-state"))),
        import_roots=tuple(Path(item) for item in raw_import_roots),
    )
    return _environment_settings(base)


def _paths_from_env(name: str) -> tuple[Path, ...] | None:
    value = os.environ.get(name)
    return None if value is None else tuple(Path(item) for item in value.split(os.pathsep) if item)


def _environment_settings(base: Settings) -> Settings:
    import_roots = _paths_from_env("REMARKABLE_IMPORT_ROOTS")
    import_host_roots = _paths_from_env("REMARKABLE_IMPORT_HOST_ROOTS")
    return Settings(
        artifact_directory=Path(os.environ.get("REMARKABLE_ARTIFACT_DIR", str(base.artifact_directory))),
        artifact_host_directory=Path(os.environ["REMARKABLE_ARTIFACT_HOST_DIR"]) if os.environ.get("REMARKABLE_ARTIFACT_HOST_DIR") else base.artifact_host_directory,
        state_directory=Path(os.environ.get("REMARKABLE_STATE_DIR", str(base.state_directory))),
        import_roots=import_roots if import_roots is not None else base.import_roots,
        import_host_roots=import_host_roots if import_host_roots is not None else base.import_host_roots,
    )
