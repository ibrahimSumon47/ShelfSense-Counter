# Data card

Status: verified (2026-11-16, S1-01).

## Rules

- No images, labels or archives are committed. Everything is downloaded by script into `training/data/` (gitignored).
- Splits are made by store or by source, never by random image, so photos of the same shelf or the same store cannot appear on both sides of a split.
- A near-duplicate check (perceptual dHash, 64-bit, Hamming distance threshold $\le 8$) runs across splits before training; its report is committed in `docs/reports/`.
- Test images are used once, for the final report.

---

## Verified datasets (checked 2026-11-16)

Licence notes: SKU-110K is for academic and non-commercial research only; any weights
trained on it carry that restriction. The detector has been fine-tuned on both sets
(torchvision FCOS ResNet-50 FPN); its validation numbers and commands are in
[reports/validation-detection-cap.md](reports/validation-detection-cap.md).

| Dataset | Scale & Density | Licence (verified 2026-11-16) | Access method | Split unit |
| --- | --- | --- | --- | --- |
| **SKU-110K** (*Goldman et al., CVPR 2019*) | 11,762 shelf images (8,219 train / 588 val / 2,936 test cleaned), ~1.73M bounding boxes (~147.4 items/image) | Academic and non-commercial research use only (Trax Retail / CC BY-NC-SA 3.0 on mirrors) | Kaggle CLI (`thedatasith/sku110k-annotations` or `mohamedessam3112002/sku-110k`) and official S3 archive (`http://trax-geometry.s3.amazonaws.com/cvpr_challenge/SKU110K_fixed.tar.gz`) | Store-disjoint official splits (`train_*`, `val_*`, `test_*`), verified with cross-split perceptual dHash |
| **Supermarket Shelves Dataset** (*Humans in the Loop*) | 45 high-resolution supermarket shelf images, ~11,743 bounding boxes (~260.9 boxes/image; `Product` and `Price` classes, filtered to `Product` only) | **CC0 1.0 Public Domain** (free for academic and commercial use) | Kaggle CLI (`humansintheloop/supermarket-shelves-dataset`) | Capture session / aisle grouping + perceptual dHash clustering (70% train / 15% val / 15% test) |
| **Grocery Dataset** (*Varol & Kuzu, 2014*, optional evaluation benchmark) | 354 shelf images across ~40 grocery stores and 4 cameras (`C<c>_P<p>_N<n>_S<s>_<i>.JPG`) | Academic / non-commercial research repository (`gulvarol/grocerydataset`, no OSI commercial license) | Direct HTTP archive / GitHub source | Planogram / store prefix `P<p>` (never split copies `<i>` of the same planogram across splits) |

### Licensing impact on trained weights

- Models trained or fine-tuned on **SKU-110K** inherit its **non-commercial research and portfolio** restriction. That matches our Vercel Hobby deployment terms and portfolio/resume scope (`docs/DECISIONS.md`, ADR-004 and ADR-009).
- Models trained exclusively on **Supermarket Shelves (HITL)** are **CC0 / commercial-permissive** and can be used in commercial Upwork client work without dataset relicensing.

---

## Target schema and label mapping

All dataset annotations are converted into a unified single-class detector format (`class_id = 0`, label `item`):

1. **SKU-110K CSV** (`image_name, x1, y1, x2, y2, class, image_width, image_height`, headerless):
   - Every valid row with $0 \le x_1 < x_2 \le W$ and $0 \le y_1 < y_2 \le H$ maps to class `0` (`item`), normalized to YOLO `(x_center, y_center, width, height)` in $[0, 1]$ and COCO JSON `[x_min, y_min, width, height]` in pixels.
2. **Supermarket Shelves (HITL)** (Supervisely JSON / COCO / VOC annotations):
   - Only `Product` (or `item`) objects are retained (`class_id = 0`); `Price` (price tag) boxes are excluded so the detector counts products rather than shelf tags.
3. **Grocery Dataset** (`annotation.txt`: `<image> <n> <x1> <y1> <x2> <y2> ...`):
   - Each of the $n$ box tuples maps to `class_id = 0`.

---

## Leak-free split design

As used by the current training config (`training/configs/fcos-dense-v3.json`):
6,000 SKU-110K `train` images (sorted by file name, deterministic), 200 SKU-110K `val`
images for threshold tuning, 200 SKU-110K `test` images and the 9 CC0 test images for the
single final evaluation, plus the 27 CC0 training images.

1. **Source and store isolation:**
   - In SKU-110K, the authors partitioned images by store so that shelves from the same physical store do not cross `train`, `val`, and `test`. We preserve those store-disjoint partitions as the primary split.
   - In Supermarket Shelves (HITL) and Grocery Dataset, images are grouped by capture prefix / planogram ID (`P<p>`) and perceptual similarity before assigning groups to `train` (70%), `val` (15%), and `test` (15%).
2. **Cross-split near-duplicate audit (S1-03):**
   - Every image in `train`, `val`, and `test` is hashed with a 64-bit difference hash (dHash, $9 \times 8$ grayscale resize).
   - Any pair of images across different splits (`train` vs `val`, `train` vs `test`, `val` vs `test`) with Hamming distance $\le 8$ is flagged as a near-duplicate leak and quarantined out of `val`/`test` (or merged into the same split group) before any training run begins.

---

## Known limitations and domain gaps

- **Single-class detection:** The datasets train a class-agnostic product detector (`item`). It counts items and locates empty shelf gaps, but does not classify brand SKUs.
- **Camera angles and lighting:** Most images are front-facing retail aisle captures; extreme oblique angles, motion blur, or deep specular glare on glass fridge doors reduce recall.
- **Packaging styles:** SKU-110K is dominated by US/European/East Asian supermarket shelves; South Asian flexible pouches and hanging sachets are less represented and will be monitored in the S3 failure-case gallery.
