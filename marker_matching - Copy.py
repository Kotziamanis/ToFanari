# -*- coding: utf-8 -*-
"""
ToFanari — Marker-based matching for Βάση Δεδομένων.

Scans chapter HTML for data-audio markers, matches them to MP3 files by numeric ID.
Used for Bunny upload, chapter merge, FlipBuilder audio placement.
"""

from __future__ import annotations

import json
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
from urllib.parse import quote

# ─── Marker detection ────────────────────────────────────────────────────────

# data-audio="001" or data-audio='001' or data-audio-id="001", etc.
# Extract numeric ID: 001, 002, 1, 2 (normalize to 3-digit)
_DATA_AUDIO_RE = re.compile(
    r'\bdata-audio(?:-id)?\s*=\s*["\']([^"\']+)["\']',
    re.IGNORECASE,
)

# Also match src/href to audio/*.mp3: extract leading digits before space or extension
# e.g. ../audio/001 Example.mp3 → 001, audio/002.mp3 → 002
_AUDIO_SRC_MP3_RE = re.compile(
    r'(?:src|href)\s*=\s*["\'][^"\']*?/(\d{1,6})(?:\s|\.mp3|["\'])',
    re.IGNORECASE,
)


def extract_marker_ids_from_html(
    html: str,
) -> Tuple[List[str], List[str]]:
    """
    Extract numeric marker IDs from HTML.
    Supports: data-audio="001", data-audio-id="002", src/href to audio/NNN*.mp3.
    Returns (ordered_unique_ids, duplicate_ids).
    - ordered_unique_ids: in order of first appearance, 3-digit (001, 002)
    - duplicate_ids: IDs that appeared more than once in HTML
    """
    seen_order: Dict[str, int] = {}
    counts: Dict[str, int] = {}
    order = [0]

    def add_id(raw: str) -> None:
        s = (raw or "").strip()
        if not s:
            return
        m = re.match(r"^(\d{1,6})", s)
        if m:
            num = int(m.group(1))
            key = f"{num:03d}"
            counts[key] = counts.get(key, 0) + 1
            if key not in seen_order:
                seen_order[key] = order[0]
                order[0] += 1

    for m in _DATA_AUDIO_RE.finditer(html):
        add_id(m.group(1))
    for m in _AUDIO_SRC_MP3_RE.finditer(html):
        add_id(m.group(1))

    ordered = sorted(seen_order.keys(), key=lambda k: seen_order[k])
    dups = [k for k, c in counts.items() if c > 1]
    return ordered, dups


def scan_html_folder_for_markers(
    folder: str,
) -> Tuple[List[str], List[str], List[str]]:
    """
    Scan folder for HTML files and extract marker IDs.
    Searches: index.html first, then html/index.html, then *.html.
    Returns (marker_ids_ordered, html_files_scanned, duplicate_marker_ids).
    """
    folder_path = Path(folder)
    if not folder_path.is_dir():
        return [], [], []

    candidates: List[Path] = []
    for p in [folder_path / "index.html", folder_path / "html" / "index.html"]:
        if p.is_file():
            candidates.append(p)
    for pat in ["*.html", "html/*.html"]:
        for p in sorted(folder_path.glob(pat)):
            if p.is_file() and p not in candidates:
                candidates.append(p)
    html_files = list(dict.fromkeys(candidates))

    all_ids: List[str] = []
    seen: set = set()
    all_dups: List[str] = []
    for p in html_files:
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        ids, dups = extract_marker_ids_from_html(text)
        for mid in ids:
            if mid not in seen:
                seen.add(mid)
                all_ids.append(mid)
        for d in dups:
            if d not in all_dups:
                all_dups.append(d)
    return all_ids, [str(p) for p in html_files], all_dups


# ─── MP3 parsing ─────────────────────────────────────────────────────────────

# Extract numeric ID from filename: audio001.mp3 → 001, 001 Title.mp3 → 001, 005.mp3 → 005
_MP3_ID_PATTERNS = [
    re.compile(r"^audio(\d{1,6})\.mp3$", re.IGNORECASE),
    re.compile(r"^(\d{1,6})\s", re.IGNORECASE),  # 001 Title.mp3
    re.compile(r"^(\d{1,6})\.mp3$", re.IGNORECASE),  # 001.mp3
    re.compile(r"^[A-Za-z0-9_-]+-(\d{1,6})\.mp3$", re.IGNORECASE),  # AN01-001.mp3
]

# Leading hymn number at start of basename; next char must not be a digit (avoids 001 vs 0010)
_MP3_LEADING_NUM_PREFIX_RE = re.compile(r"^(\d{1,6})(?!\d)", re.IGNORECASE)


def sort_mp3_filenames_by_numeric_prefix(filenames: List[str]) -> List[str]:
    """
    Sort MP3 basenames by leading hymn number (001, 002, … 010, … 100).
    Files without a leading numeric prefix sort last (lexicographic).
    """
    def sort_key(fn: str) -> tuple:
        base = os.path.basename(fn)
        m = _MP3_LEADING_NUM_PREFIX_RE.match(base)
        if m:
            return (0, int(m.group(1)), base.lower())
        m2 = re.match(r"^(\d+)", base)
        if m2:
            return (1, int(m2.group(1)), base.lower())
        return (2, 0, base.lower())

    return sorted(filenames, key=sort_key)


def build_mp3_prefix_map(filenames: List[str]) -> Dict[str, str]:
    """
    Map 3-digit hymn id → actual .mp3 basename (first file wins per id).
    Uses leading numeric prefix at start of filename (001 Kyrie.mp3, 001.mp3, 001Kyrie.mp3);
    does not treat 0010… as id 001.
    """
    out: Dict[str, str] = {}
    for fn in sort_mp3_filenames_by_numeric_prefix(filenames):
        base = os.path.basename(fn)
        mid = extract_mp3_id(fn)
        if not mid:
            continue
        if mid not in out:
            out[mid] = base
    return out


def extract_mp3_id(filename: str) -> Optional[str]:
    """
    Extract numeric ID from MP3 filename.
    Returns 3-digit string (001, 002) or None if no match.
    Prefers leading prefix at basename start (Step 5 / source files like "001 title.mp3").
    """
    if not filename or not filename.lower().endswith(".mp3"):
        return None
    base = os.path.basename(filename)
    m = _MP3_LEADING_NUM_PREFIX_RE.match(base)
    if m:
        num = int(m.group(1))
        if num > 0:
            return f"{num:03d}"
    for pat in _MP3_ID_PATTERNS:
        m = pat.match(base)
        if m:
            num = int(m.group(1))
            return f"{num:03d}"
    return None


def parse_mp3_folder(
    mp3_folder: str,
) -> Tuple[Dict[str, str], Dict[str, List[str]]]:
    """
    Scan MP3 folder and build mapping: marker_id -> mp3_filename.
    If duplicate IDs (multiple files map to same ID), first file wins; rest are in duplicates.
    Returns (id_to_file, id_to_all_files_for_duplicates).
    """
    if not mp3_folder or not os.path.isdir(mp3_folder):
        return {}, {}
    result: Dict[str, str] = {}
    all_per_id: Dict[str, List[str]] = {}
    try:
        files = sort_mp3_filenames_by_numeric_prefix(
            f for f in os.listdir(mp3_folder)
            if os.path.isfile(os.path.join(mp3_folder, f)) and f.lower().endswith(".mp3")
        )
    except OSError:
        return {}, {}
    for f in files:
        mid = extract_mp3_id(f)
        if not mid:
            continue
        all_per_id.setdefault(mid, []).append(f)
        if mid not in result:
            result[mid] = f
    return result, all_per_id


# ─── Matching and validation ─────────────────────────────────────────────────

@dataclass
class MarkerMatch:
    """Single marker-to-MP3 match record."""
    marker_id: str
    mp3_filename: str
    status: str  # OK, NO_AUDIO, NO_MARKER, DUPLICATE_MARKER, DUPLICATE_MP3


@dataclass
class MarkerMatchingResult:
    """Full result of marker matching and validation."""
    marker_ids: List[str] = field(default_factory=list)  # from HTML, ordered
    mp3_id_to_file: Dict[str, str] = field(default_factory=dict)
    matches: List[MarkerMatch] = field(default_factory=list)
    markers_without_audio: List[str] = field(default_factory=list)
    audio_without_marker: List[str] = field(default_factory=list)
    duplicate_markers: List[str] = field(default_factory=list)
    duplicate_mp3_ids: List[str] = field(default_factory=list)
    html_files_scanned: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def match_markers_to_mp3(
    html_folder: str,
    mp3_folder: str,
) -> MarkerMatchingResult:
    """
    Detect markers from HTML, parse MP3 folder, match by ID, validate.
    Returns MarkerMatchingResult with matches, issues, and summary.
    """
    r = MarkerMatchingResult()

    # 1. Scan HTML
    marker_ids, html_files, dup_markers = scan_html_folder_for_markers(html_folder)
    r.marker_ids = marker_ids
    r.html_files_scanned = html_files
    r.duplicate_markers = dup_markers

    if not html_folder or not os.path.isdir(html_folder):
        r.errors.append("HTML folder is missing or invalid.")
        return r
    if not marker_ids:
        r.warnings.append("No audio markers found in HTML. Expected data-audio=\"001\" or similar.")

    # 2. Parse MP3 folder
    mp3_id_to_file, all_per_id = parse_mp3_folder(mp3_folder)
    r.mp3_id_to_file = mp3_id_to_file

    if not mp3_folder or not os.path.isdir(mp3_folder):
        r.errors.append("MP3 folder is missing or invalid.")
    elif not mp3_id_to_file:
        r.warnings.append("No MP3 files with extractable IDs found in folder.")

    # Duplicate MP3 IDs: multiple files map to same ID
    for mid, fns in all_per_id.items():
        if len(fns) > 1:
            r.duplicate_mp3_ids.append(f"{mid}: {', '.join(fns)}")

    # 3. Build matches (one row per marker, in marker order)
    for mid in marker_ids:
        fn = mp3_id_to_file.get(mid)
        if fn:
            dup = len(all_per_id.get(mid, [])) > 1
            status = "DUPLICATE_MP3" if dup else "OK"
            r.matches.append(MarkerMatch(marker_id=mid, mp3_filename=fn, status=status))
        else:
            r.matches.append(MarkerMatch(marker_id=mid, mp3_filename="", status="NO_AUDIO"))
            r.markers_without_audio.append(mid)

    # 4. Audio without marker (MP3 exists but no marker in HTML)
    matched_marker_ids = set(marker_ids)
    for mid, fn in mp3_id_to_file.items():
        if mid not in matched_marker_ids:
            r.audio_without_marker.append(f"{mid} ({fn})")
            r.matches.append(MarkerMatch(marker_id=mid, mp3_filename=fn, status="NO_MARKER"))

    # Sort matches: OK first (by marker order), then NO_AUDIO, then NO_MARKER
    def order_key(m: MarkerMatch) -> tuple:
        if m.status == "OK":
            return 0, marker_ids.index(m.marker_id) if m.marker_id in marker_ids else 999
        if m.status == "NO_AUDIO":
            return 1, marker_ids.index(m.marker_id) if m.marker_id in marker_ids else 999
        return 2, 0

    r.matches.sort(key=order_key)

    return r


def format_matching_report(result: MarkerMatchingResult) -> List[str]:
    """Produce a text report for UI display."""
    lines = [
        "MARKER MATCHING REPORT",
        "",
        f"Detected markers: {len(result.marker_ids)}",
        f"Matched audio files: {len(result.mp3_id_to_file)}",
        "",
    ]
    if result.markers_without_audio:
        lines.append("--- Markers with no audio ---")
        lines.extend(result.markers_without_audio)
        lines.append("")
    if result.audio_without_marker:
        lines.append("--- Audio with no marker ---")
        lines.extend(result.audio_without_marker)
        lines.append("")
    if result.duplicate_markers:
        lines.append("--- Duplicate markers (in HTML) ---")
        lines.extend(result.duplicate_markers)
        lines.append("")
    if result.duplicate_mp3_ids:
        lines.append("--- Duplicate MP3 IDs ---")
        lines.extend(result.duplicate_mp3_ids)
        lines.append("")
    if result.errors:
        lines.append("--- Errors ---")
        lines.extend(result.errors)
        lines.append("")
    if result.warnings:
        lines.append("--- Warnings ---")
        lines.extend(result.warnings)
        lines.append("")
    ok = sum(1 for m in result.matches if m.status == "OK")
    lines.append(f"Summary: {ok} OK, {len(result.markers_without_audio)} markers without audio, "
                 f"{len(result.audio_without_marker)} audio without marker.")
    return lines


# ─── PDF markers ↔ plain MP3 (001.mp3) — 2-stage workflow (pre / post Bunny) ─

PREUPLOAD_AUDIO_MAPPING_JSON = "preupload_audio_mapping.json"
PREUPLOAD_AUDIO_VALIDATION_JSON = "preupload_audio_validation.json"
POSTUPLOAD_AUDIO_MAPPING_JSON = "postupload_audio_mapping.json"

# Stage 1: only filenames like 001.mp3, 023.mp3 (strict; no BOOK-001, no "001 Title.mp3")
_PLAIN_NUMERIC_MP3_RE = re.compile(r"^(\d{1,6})\.mp3$", re.IGNORECASE)


def format_id(value: Any) -> str:
    """Normalize a numeric marker/audio id to 3-digit string (1 -> 001). Rejects <= 0."""
    if value is None:
        raise ValueError("format_id: value must not be None")
    if isinstance(value, bool):
        raise ValueError("format_id: bool not allowed")
    if isinstance(value, int):
        n = int(value)
        if n <= 0:
            raise ValueError("format_id: id must be >= 1")
        return f"{n:03d}"
    s = str(value).strip()
    if not s or not s.isdigit():
        raise ValueError(f"format_id: not a positive integer string: {value!r}")
    n = int(s)
    if n <= 0:
        raise ValueError("format_id: id must be >= 1")
    return f"{n:03d}"


def normalize_marker_id(marker_id: Any) -> Optional[str]:
    """
    Return 3-digit id string, or None if missing/invalid.
    Accepts int, or digit-only str (e.g. 1, "001", "02").
    """
    if marker_id is None:
        return None
    if isinstance(marker_id, bool):
        return None
    try:
        if isinstance(marker_id, int):
            if marker_id <= 0:
                return None
            return f"{marker_id:03d}"
        s = str(marker_id).strip()
        if not s or not s.isdigit():
            return None
        n = int(s)
        if n <= 0:
            return None
        return f"{n:03d}"
    except (TypeError, ValueError):
        return None


def extract_audio_id(filename: str) -> Optional[str]:
    """
    Extract 3-digit id from basename only: 001.mp3 -> 001.
    Invalid / other patterns -> None.
    """
    if not filename:
        return None
    base = os.path.basename(filename.strip())
    m = _PLAIN_NUMERIC_MP3_RE.match(base)
    if not m:
        return None
    return f"{int(m.group(1)):03d}"


def scan_plain_mp3_ids(audio_folder: str) -> Tuple[Dict[str, List[str]], int]:
    """
    List .mp3 in folder (non-recursive). Map id -> filenames for plain NNN.mp3 only.
    Returns (id_to_filenames, total_mp3_count_in_folder).
    """
    id_to_files: Dict[str, List[str]] = {}
    total_mp3 = 0
    if not audio_folder or not os.path.isdir(audio_folder):
        return id_to_files, total_mp3
    try:
        names = sorted(
            f
            for f in os.listdir(audio_folder)
            if os.path.isfile(os.path.join(audio_folder, f)) and f.lower().endswith(".mp3")
        )
    except OSError:
        return id_to_files, total_mp3
    total_mp3 = len(names)
    for f in names:
        aid = extract_audio_id(f)
        if aid is None:
            continue
        id_to_files.setdefault(aid, []).append(f)
    return id_to_files, total_mp3


def build_bunny_audio_url(base_url: str, filename: str) -> str:
    """Safe public URL: base + / + encoded basename. Empty if inputs invalid."""
    base = (base_url or "").strip().rstrip("/")
    fn = os.path.basename((filename or "").strip())
    if not base or not fn:
        return ""
    return f"{base}/{quote(fn, safe='')}"


def validate_local_audio_matches(
    markers: List[Any],
    audio_folder: str,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Stage 1: PDF markers (pdf_ops.Marker with number/page/x/y) vs plain 001.mp3 files.
    Strict ID match only. Returns (mapping_rows, validation_report).
    """
    # Local import would be circular if pdf_ops imported marker_matching; it does not.
    from pdf_ops import get_active_markers

    active = get_active_markers(list(markers or []))
    id_to_files, total_mp3 = scan_plain_mp3_ids(audio_folder)

    marker_rows: List[Tuple[Any, str]] = []
    for i, m in enumerate(active):
        # Explicit checks — never use `if not m.number` (would skip valid numbering edge cases).
        num = m.number
        if num is None or not isinstance(num, int) or num <= 0:
            num = i + 1  # order-based fallback; includes index 0 -> id 001
        mid = format_id(num)
        marker_rows.append((m, mid))

    ordered_ids = [mid for _, mid in marker_rows]
    id_counts = Counter(ordered_ids)
    duplicate_marker_ids = sorted(k for k, c in id_counts.items() if c > 1)

    duplicate_audio_ids = sorted(k for k, files in id_to_files.items() if len(files) > 1)
    single_audio: Dict[str, str] = {
        k: files[0] for k, files in id_to_files.items() if len(files) == 1
    }

    marker_id_set = set(ordered_ids)
    orphan_audio_ids = sorted(k for k in id_to_files if k not in marker_id_set)

    mapping: List[Dict[str, Any]] = []
    missing_audio_ids: List[str] = []

    for m, mid in marker_rows:
        page = int(m.page) if m.page is not None else 0
        x = float(m.x)
        y = float(m.y)
        if mid in duplicate_marker_ids:
            status = "duplicate_marker"
            audio_file = ""
        elif mid in duplicate_audio_ids:
            status = "duplicate_audio"
            audio_file = ""
        elif mid in single_audio:
            status = "matched_local"
            audio_file = single_audio[mid]
        else:
            status = "missing_audio"
            audio_file = ""
            missing_audio_ids.append(mid)

        mapping.append(
            {
                "id": mid,
                "page": page,
                "x": x,
                "y": y,
                "audio_file": audio_file,
                "status": status,
            }
        )

    matched_count = sum(1 for row in mapping if row.get("status") == "matched_local")
    total_markers = len(marker_rows)
    plain_named = sum(len(v) for v in id_to_files.values())

    ready_for_upload = (
        len(missing_audio_ids) == 0
        and len(duplicate_marker_ids) == 0
        and len(duplicate_audio_ids) == 0
        and total_markers > 0
    )

    report: Dict[str, Any] = {
        "total_markers": total_markers,
        "total_audio_files": total_mp3,
        "matched_count": matched_count,
        "missing_audio_ids": sorted(set(missing_audio_ids)),
        "orphan_audio_ids": orphan_audio_ids,
        "duplicate_marker_ids": duplicate_marker_ids,
        "duplicate_audio_ids": duplicate_audio_ids,
        "ready_for_upload": ready_for_upload,
        "plain_id_mp3_files": plain_named,
        "unparsed_mp3_count": max(0, total_mp3 - plain_named),
    }
    return mapping, report


def save_preupload_json(mapping: List[Dict[str, Any]], path: str) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=2, ensure_ascii=False)


def save_validation_report_json(report: Dict[str, Any], path: str) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)


def run_stage1_preupload_save(
    work_folder: str,
    markers: List[Any],
    audio_folder: str,
) -> Tuple[str, str, Dict[str, Any]]:
    """
    Run validation and write preupload_audio_mapping.json + preupload_audio_validation.json.
    Returns (mapping_path, report_path, report_dict).
    """
    mapping, report = validate_local_audio_matches(markers, audio_folder)
    wf = (work_folder or "").strip()
    if not wf:
        raise ValueError("work_folder is required to save pre-upload JSON")
    os.makedirs(wf, exist_ok=True)
    map_path = os.path.join(wf, PREUPLOAD_AUDIO_MAPPING_JSON)
    rep_path = os.path.join(wf, PREUPLOAD_AUDIO_VALIDATION_JSON)
    save_preupload_json(mapping, map_path)
    save_validation_report_json(report, rep_path)
    return map_path, rep_path, report


def create_remote_mapping(
    local_mapping: Sequence[Dict[str, Any]],
    bunny_base_url: str,
    uploaded_filenames: Optional[Set[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Stage 2: only rows with status matched_local become matched_remote with audio_url.
    If uploaded_filenames is set, require audio_file in that set (basename match).
    """
    out: List[Dict[str, Any]] = []
    allowed: Optional[Set[str]] = None
    if uploaded_filenames is not None:
        allowed = {os.path.basename(x) for x in uploaded_filenames if x}

    for row in local_mapping:
        if (row.get("status") or "") != "matched_local":
            continue
        fn = (row.get("audio_file") or "").strip()
        if not fn:
            continue
        base_name = os.path.basename(fn)
        if allowed is not None and base_name not in allowed:
            continue
        url = build_bunny_audio_url(bunny_base_url, base_name)
        if not url:
            continue
        out.append(
            {
                "id": row.get("id"),
                "page": row.get("page"),
                "x": row.get("x"),
                "y": row.get("y"),
                "audio_file": base_name,
                "audio_url": url,
                "status": "matched_remote",
            }
        )
    return out


def load_preupload_mapping(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("pre-upload mapping must be a JSON array")
    return data


def run_stage2_postupload_save(
    work_folder: str,
    bunny_base_url: str,
    uploaded_filenames: Optional[Set[str]] = None,
    preupload_mapping_path: Optional[str] = None,
) -> str:
    """
    Load preupload_audio_mapping.json from work_folder (or preupload_mapping_path),
    build remote rows, write postupload_audio_mapping.json. Returns output path.
    """
    wf = (work_folder or "").strip()
    path = preupload_mapping_path or os.path.join(wf, PREUPLOAD_AUDIO_MAPPING_JSON)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Pre-upload mapping not found: {path}")
    local_rows = load_preupload_mapping(path)
    remote = create_remote_mapping(local_rows, bunny_base_url, uploaded_filenames)
    out_dir = wf or os.path.dirname(os.path.abspath(path))
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, POSTUPLOAD_AUDIO_MAPPING_JSON)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(remote, f, indent=2, ensure_ascii=False)
    return out_path
