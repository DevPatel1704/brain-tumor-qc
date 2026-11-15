"""Small axial PNG thumbnails for the review queue (served locally, cached on disk).

The slice passes through the tumor centroid when a prediction (or reference mask)
exists, otherwise through the middle of the brain. Display matches the viewer:
canonical RAS, radiological (patient right on the left, anterior at the top), the
FLAIR viewer bundle (already windowed to the 1st-99th percentile), and the label
outline in the viewer colors. No dependency beyond numpy and the standard library.
"""

from __future__ import annotations

import struct
import zlib
from typing import TYPE_CHECKING

import numpy as np

from btqc.data.convert import read_bundle

if TYPE_CHECKING:
    from btqc.serve.store import Store

SEG_RGB = {1: (229, 72, 77), 2: (46, 189, 89), 3: (242, 204, 58), 4: (242, 204, 58)}


def png_bytes(rgb: np.ndarray) -> bytes:
    """Encode an (h, w, 3) uint8 array as an 8-bit RGB PNG."""
    h, w, _ = rgb.shape
    rows = np.ascontiguousarray(rgb, dtype=np.uint8)
    raw = b"".join(b"\x00" + rows[r].tobytes() for r in range(h))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def _display(sl: np.ndarray) -> np.ndarray:
    """[x, y] canonical slice -> [row, col] radiological display."""
    return sl[::-1, ::-1].T


def render_thumbnail(img: np.ndarray, seg: np.ndarray | None, size: int = 96) -> np.ndarray:
    """(nx, ny, nz) uint8 volume and optional labels -> (size, size, 3) uint8 axial thumbnail."""
    brain = img > 0
    if seg is not None and (seg > 0).any():
        z = round(float(np.argwhere(seg > 0)[:, 2].mean()))
    else:
        zs = np.flatnonzero(brain.any(axis=(0, 1)))
        z = (int(zs[0]) + int(zs[-1])) // 2 if len(zs) else img.shape[2] // 2
    gray = _display(img[:, :, z]).astype(np.float32)
    lab = _display(seg[:, :, z]) if seg is not None else None
    rr, cc = np.nonzero(gray > 0)
    if len(rr):
        r0, r1, c0, c1 = int(np.min(rr)), int(np.max(rr)) + 1, int(np.min(cc)), int(np.max(cc)) + 1
    else:
        r0, r1, c0, c1 = 0, gray.shape[0], 0, gray.shape[1]
    side = int(max(r1 - r0, c1 - c0) * 1.08) + 2
    cr, ccen = (r0 + r1) / 2, (c0 + c1) / 2
    # 2x supersampled nearest-neighbour grid, then a 2x2 box filter for the image
    n2 = size * 2
    pos = (np.arange(n2) + 0.5) / n2 * side - side / 2
    ri, ci = np.floor(cr + pos).astype(int), np.floor(ccen + pos).astype(int)
    valid = (ri[:, None] >= 0) & (ri[:, None] < gray.shape[0]) & (ci[None, :] >= 0) & (ci[None, :] < gray.shape[1])
    rs, cs = np.clip(ri, 0, gray.shape[0] - 1), np.clip(ci, 0, gray.shape[1] - 1)
    big = np.where(valid, gray[rs[:, None], cs[None, :]], 0.0)
    small = big.reshape(size, 2, size, 2).mean(axis=(1, 3))
    out = np.repeat(small[:, :, None], 3, axis=2)
    if lab is not None:
        lb = np.where(valid, lab[rs[:, None], cs[None, :]], 0)[::2, ::2]
        edge = np.zeros_like(lb, dtype=bool)
        edge[1:, :] |= lb[1:, :] != lb[:-1, :]
        edge[:-1, :] |= lb[:-1, :] != lb[1:, :]
        edge[:, 1:] |= lb[:, 1:] != lb[:, :-1]
        edge[:, :-1] |= lb[:, :-1] != lb[:, 1:]
        for v, col in SEG_RGB.items():
            m = (lb == v) & edge
            out[m] = col
    return np.clip(np.rint(out), 0, 255).astype(np.uint8)


def case_thumbnail(store: Store, cid: str, size: int = 96) -> bytes:
    """PNG bytes for a case, cached under <processed>/thumbs. Raises NotFound for unknown cases."""
    from btqc.serve.store import NotFound, safe_id

    seqs = store.sequences(safe_id(cid))
    if not seqs:
        raise NotFound(cid)
    seq = "flair" if "flair" in seqs else seqs[0]
    vdir = store.viewer / cid
    hit = store.find_prediction(cid)
    sources = [vdir / f"{seq}.u8.gz"] + ([hit[2] / f"{cid}.npz"] if hit else [])
    out = store.processed / "thumbs" / f"{cid}_{size}.png"
    if out.exists() and all(out.stat().st_mtime >= p.stat().st_mtime for p in sources if p.exists()):
        return out.read_bytes()
    img, _ = read_bundle(vdir, seq)
    seg: np.ndarray | None = None
    got = store.prediction(cid)
    if got is not None:
        seg = np.asarray(got[2].seg, dtype=np.uint8)
    elif store.has_reference(cid):
        seg = read_bundle(vdir, "seg")[0]
    data = png_bytes(render_thumbnail(img, seg, size))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    return data
