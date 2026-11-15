## 9. Reviewer notes (checked by hand after the generated sections)

These notes come from follow-up inspection commands run on `data/file_inventory.csv` and the raw headers on 2026-10-31.

- **Affines.** The 4 "distinct" affines differ only in the sign of zero entries (`-0.0` vs `0.0`). Numerically they are all `diag(-1, -1, 1)` with offset `(0, 239, 0)`, so every file is LPS and canonical RAS needs flips of the first two axes.
- **sform.** 232 files (58 cases) have `sform_code = 0`. For them the qform is used, and it encodes the same LPS affine. The reader applies sform first, then qform (Appendix A of the brief), in Python and in the browser.
- **dtype.** 159 files (40 cases) are stored as float32, the rest as int16. Some cases mix the two across sequences. Canonical copies keep each file's dtype.
- **`descrip` field.** It is non-empty in 12 files (3 cases) and holds a processing-software tag, not an identifier. Free-text fields are never copied to outputs regardless of content.
- **Negative intensities.** `FeTS2022_00467` T2 (min −43) and `FeTS2022_01771` FLAIR (min −36.1) have a few negative voxels, likely interpolation ringing near the brain edge. Viewer bundles map every nonzero voxel to 1..255, so these stay distinct from the exact-zero background.
- **Intensity scale.** Raw intensity scales differ by two orders of magnitude between cases (median p99 of T1 is 593, maximum 25,310). This is acquisition and processing heterogeneity, which per-case z-scoring (nnU-Net) removes before the network sees the data.
- **Inner file names.** 36 cases (144 files) carry an inner file name `<8 digits>_brain_<seq>.nii` that differs from the official `FeTS2022_<id>` wrapper name. All four sequences of each case agree. The official wrapper name is used as the case id. The inner names are kept only in the local inventory and never served by the API.
- **Pre-existing PNGs.** The 155 PNG files are axial FLAIR slices of `FeTS2022_00027`, found inside the raw folder. They are not used.
