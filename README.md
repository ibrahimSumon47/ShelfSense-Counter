# ShelfSense

Count what is on a retail shelf from a single photo.

> **Status: not measured yet; pipeline demonstration only.** No trained detector exists yet,
> so no accuracy figure is published and the public site does not analyse photos. An earlier
> version of this repository reported detection metrics that came from a simulation; they
> were withdrawn. The full account is in [docs/LESSONS.md](docs/LESSONS.md).

Live site (shows the interface only, no detection): https://shelfsense-counter.vercel.app

## Goal

Take or upload a picture of a grocery shelf and find each product, count them, mark gaps
and flag low stock per store, aisle and shelf, with a chat that answers questions about
stored scans in English or Bangla.

## What exists and works today

- Dashboard shell (English and Bangla, dark and light themes) with the detector disabled.
- Gap-from-spacing logic and CSV export, covered by unit tests (logic only, not accuracy).
- Leak-free dataset split tooling and annotation converters, with tests.
- A Python package and CLI. Without a model file the CLI uses a contrast heuristic that
  only works on clean synthetic images and prints a warning.
- Repository hygiene: single author, secret scanning, CI.

## What does not exist yet

- A trained and evaluated detector, weights, and any mAP or count-error figure.
- Persistence (database), real authentication, thumbnail upload, trend charts.
- A measured evaluation of the chat against a real language model.

The plan and status of each item are in [docs/features.json](docs/features.json) and
[docs/HANDOFF.md](docs/HANDOFF.md).

## Licences

Code is MIT ([LICENSE](LICENSE)). Datasets and any future weights follow
[docs/DATA.md](docs/DATA.md); SKU-110K is for non-commercial research only.
