"""Find NIfTI files under a root directory and group them into cases.

File names are parsed into ``case_id`` and ``sequence``. Supported patterns
(case-insensitive, ``.nii`` or ``.nii.gz``)::

    00000096_brain_t1.nii         -> case 00000096,        sequence t1
    BraTS2021_00000_t1ce.nii.gz   -> case BraTS2021_00000, sequence t1ce
    FeTS2022_00000_flair.nii.gz   -> case FeTS2022_00000,  sequence flair
    FeTS2022_00000_seg.nii.gz     -> case FeTS2022_00000,  sequence seg

Anything else is reported as *unparsed*; nothing is guessed.

The FeTS 2022 validation download used in this project wraps every file in a
directory that carries the official name, e.g.
``FeTS2022_00027/FeTS2022_00027_flair.nii/00000019_brain_flair.nii``. When a
file sits inside such a wrapper directory, the wrapper name is the declared
identity of the file and the inner name is kept as ``inner_name``. The two
must agree on the sequence, otherwise the file is reported as a conflict.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

SEQUENCES: tuple[str, ...] = ("t1", "t1ce", "t2", "flair")
ALL_KINDS: tuple[str, ...] = (*SEQUENCES, "seg")

# Aliases seen in BraTS-family releases. Only unambiguous ones are listed.
_ALIASES = {"t1gd": "t1ce", "t1c": "t1ce"}

_NAME_RE = re.compile(
    r"^(?P<case>[A-Za-z0-9]+(?:_[A-Za-z0-9]+)*?)"
    r"(?:_brain)?"
    r"_(?P<seq>t1ce|t1gd|t1c|t1|t2|flair|seg)"
    r"\.nii(?:\.gz)?$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ParsedName:
    case_id: str
    sequence: str


def is_nifti_name(name: str) -> bool:
    low = name.lower()
    return low.endswith(".nii") or low.endswith(".nii.gz")


def parse_filename(name: str) -> ParsedName | None:
    """Parse a NIfTI file name into case id and sequence, or return None."""
    m = _NAME_RE.match(name)
    if m is None:
        return None
    seq = m.group("seq").lower()
    seq = _ALIASES.get(seq, seq)
    return ParsedName(case_id=m.group("case"), sequence=seq)


@dataclass
class FileEntry:
    path: Path
    case_id: str
    sequence: str
    declared_name: str
    inner_name: str | None = None


@dataclass
class CaseFiles:
    case_id: str
    files: dict[str, FileEntry] = field(default_factory=dict)

    @property
    def has_all_sequences(self) -> bool:
        return all(s in self.files for s in SEQUENCES)

    @property
    def has_seg(self) -> bool:
        return "seg" in self.files

    @property
    def missing(self) -> list[str]:
        return [s for s in SEQUENCES if s not in self.files]


@dataclass
class Discovery:
    root: Path
    cases: dict[str, CaseFiles]
    unparsed: list[Path]
    conflicts: list[str]
    duplicates: list[str]
    other_files: dict[str, int]


def _iter_files(root: Path) -> Iterable[Path]:
    for dirpath, _dirnames, filenames in os.walk(root):
        for fn in filenames:
            yield Path(dirpath) / fn


def classify_file(path: Path) -> tuple[FileEntry | None, str | None]:
    """Return (entry, problem). Exactly one of them is not None for NIfTI files."""
    own = parse_filename(path.name)
    parent = path.parent
    wrapper = parse_filename(parent.name) if is_nifti_name(parent.name) else None
    if wrapper is not None:
        if own is not None and own.sequence != wrapper.sequence:
            return None, (
                f"sequence conflict: wrapper {parent.name} vs inner {path.name}"
            )
        return (
            FileEntry(
                path=path,
                case_id=wrapper.case_id,
                sequence=wrapper.sequence,
                declared_name=parent.name,
                inner_name=path.name,
            ),
            None,
        )
    if own is None:
        return None, None
    return FileEntry(path=path, case_id=own.case_id, sequence=own.sequence, declared_name=path.name), None


def discover(root: str | os.PathLike[str]) -> Discovery:
    """Walk ``root`` and group NIfTI files into cases. Read-only."""
    root = Path(root)
    cases: dict[str, CaseFiles] = {}
    unparsed: list[Path] = []
    conflicts: list[str] = []
    duplicates: list[str] = []
    other: dict[str, int] = {}
    for path in _iter_files(root):
        if not is_nifti_name(path.name):
            ext = path.suffix.lower() or "<none>"
            other[ext] = other.get(ext, 0) + 1
            continue
        entry, problem = classify_file(path)
        if problem is not None:
            conflicts.append(f"{path.relative_to(root)}: {problem}")
            continue
        if entry is None:
            unparsed.append(path)
            continue
        case = cases.setdefault(entry.case_id, CaseFiles(entry.case_id))
        if entry.sequence in case.files:
            duplicates.append(
                f"{entry.case_id}/{entry.sequence}: {case.files[entry.sequence].path} and {path}"
            )
            continue
        case.files[entry.sequence] = entry
    return Discovery(
        root=root,
        cases=dict(sorted(cases.items())),
        unparsed=sorted(unparsed),
        conflicts=conflicts,
        duplicates=duplicates,
        other_files=other,
    )
