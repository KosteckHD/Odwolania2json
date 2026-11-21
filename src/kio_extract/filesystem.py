import os
from collections.abc import Iterator
from pathlib import Path

from .contracts import ConfigurationError


def _raise_scan_error(error: OSError) -> None:
    raise error


def pdf_files(root: Path) -> Iterator[Path]:
    for folder, directories, files in root.walk(on_error=_raise_scan_error):
        directories[:] = sorted(name for name in directories if not (folder / name).is_junction())
        for name in sorted(files):
            path = folder / name
            if path.suffix.lower() == ".pdf" and not path.is_symlink() and path.is_file():
                yield path


def output_paths(input_dir: Path, output_dir: Path) -> list[tuple[Path, Path]]:
    if not input_dir.is_dir():
        raise ConfigurationError(f"Katalog wejściowy nie istnieje: {input_dir}")
    if input_dir.is_relative_to(output_dir) or output_dir.is_relative_to(input_dir):
        raise ConfigurationError("Katalogi wejściowy i wyjściowy muszą być rozłączne")

    jobs = []
    seen_paths = set()
    for path in pdf_files(input_dir):
        destination = output_dir / path.relative_to(input_dir).with_suffix(".json")
        if not destination.parent.resolve().is_relative_to(output_dir):
            raise ConfigurationError(f"Katalog wynikowy wychodzi poza output: {destination.parent}")
        key = os.path.normcase(str(destination.parent.resolve() / destination.name))
        if key in seen_paths:
            raise ConfigurationError(f"Kilka PDF-ów wskazuje na ten sam wynik: {destination}")
        seen_paths.add(key)
        jobs.append((path, destination))
    return jobs
