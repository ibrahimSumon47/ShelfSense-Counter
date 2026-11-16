# ShelfSense

Count what is on a retail shelf from a single photo.

Take or upload a picture of a grocery shelf and ShelfSense finds each product, counts
them, marks empty gaps and flags shelves that are running low. Scans are saved per
store, aisle and shelf, and you can ask questions about them in English or Bangla
("which shelf is lowest today?").

> Status: in development. This README will carry the live link, measured accuracy and
> screenshots once each part is finished and measured. No number appears here without
> a committed report behind it.

## How it is put together

- **Detector** trained on open shelf datasets, exported to ONNX and run in the browser,
  so photos stay on the device.
- **Web app** (Next.js) for capture, results, history, low-stock alerts and the chat.
- **Python package and CLI** (`shelfsense count photo.jpg`) and a small FastAPI service
  for batch jobs.

Design decisions and their reasons are in [docs/DECISIONS.md](docs/DECISIONS.md).

## Licence

Code is MIT ([LICENSE](LICENSE)). Model weights follow the licences of the datasets
they were trained on; see [docs/DATA.md](docs/DATA.md).
