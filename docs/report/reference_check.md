# Reference verification (2026-10-31)

Every reference in the report was checked before citing. DOIs were resolved through `https://doi.org/<doi>` (HTTP 302 to the publisher means the DOI exists). arXiv IDs were looked up with the arXiv API, and the returned title was compared with the citation.

| Ref | Identifier | Check | Returned title / status |
|---|---|---|---|
| Amershi et al. 2019 | doi:10.1109/ICSE-SEIP.2019.00042 | doi.org 302 | resolves |
| Sculley et al. 2015 | NeurIPS paper page 5656 | HTTP 200 | "Hidden Technical Debt in Machine Learning Systems" |
| Breck et al. 2017 | doi:10.1109/BigData.2017.8258038 | doi.org 302, Crossref | "The ML test score: A rubric for ML production readiness and technical debt reduction" |
| Menze et al. 2015 | doi:10.1109/TMI.2014.2377694 | doi.org 302 | resolves |
| Bakas et al. 2017 | doi:10.1038/sdata.2017.117 | doi.org 302 | resolves |
| Baid et al. 2021 | arXiv:2107.02314 | arXiv API | "The RSNA-ASNR-MICCAI BraTS 2021 Benchmark on Brain Tumor Segmentation and Radiogenomic Classification" |
| Isensee et al. 2021 | doi:10.1038/s41592-020-01008-z | doi.org 302 | resolves |
| Ronneberger et al. 2015 | doi:10.1007/978-3-319-24574-4_28 | doi.org 302 | resolves |
| Pati et al. 2021 (FeTS) | arXiv:2105.05874 | arXiv API | "The Federated Tumor Segmentation (FeTS) Challenge" |
| Pati et al. 2022 | doi:10.1038/s41467-022-33407-5 | doi.org 302 | resolves |
| Bakas et al. 2018 | arXiv:1811.02629 | arXiv API | "Identifying the Best Machine Learning Algorithms for Brain Tumor Segmentation, ..." |
| Campello et al. 2021 | doi:10.1109/TMI.2021.3090082 | doi.org 302 | resolves |
| Ali et al. 2023 | doi:10.1038/s41597-023-01981-y | doi.org 302 | resolves |
| Manthe et al. 2024 | arXiv:2410.17265 | arXiv API | "Federated brain tumor segmentation: an extensive benchmark" |
| Zhou et al. 2023 | doi:10.1109/TPAMI.2022.3195549 | doi.org 302 | resolves |
| Chen et al. 2022 (MaxStyle) | doi:10.1007/978-3-031-16443-9_15 | doi.org 302 | resolves |
| Lakshminarayanan et al. 2017 | arXiv:1612.01474 | arXiv API | "Simple and Scalable Predictive Uncertainty Estimation using Deep Ensembles" |
| Gal and Ghahramani 2016 | arXiv:1506.02142 | arXiv API | "Dropout as a Bayesian Approximation: ..." |
| Guo et al. 2017 | arXiv:1706.04599 | arXiv API | "On Calibration of Modern Neural Networks" |
| Jungo and Reyes 2019 | doi:10.1007/978-3-030-32245-8_6 | doi.org 302 | resolves |
| Lewis et al. 2020 | arXiv:2005.11401 | arXiv API | "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks" |
| Wang et al. 2021 (Tent) | arXiv:2006.10726 | arXiv API | "Tent: Fully Test-time Adaptation by Entropy Minimization" |
| Isensee et al. 2018 (No New-Net) | arXiv:1809.10483 | arXiv API | "No New-Net" |
| FANCL (HD95 penalty usage) | arXiv:2410.22057 | arXiv API | "FANCL: Feature-Guided Attention Network with Curriculum Learning for Brain Metastases Segmentation" |
| BraTS 2023 glioma winner (HD95 374) | arXiv:2402.17317 | arXiv API | "How we won BraTS 2023 Adult Glioma challenge? Just faking it! ..." |
