# Demo Script (3-Minute Walkthrough)

A short walkthrough for demonstrating **ShelfSense** live on a portfolio call or screen recording.

## 1. Problem & Architecture (30s)

- Retail staff spend hours manually counting items on grocery shelves and spotting out-of-stock voids.
- **ShelfSense** runs an int8-quantized YOLOX single-class product detector directly **inside the browser** via `onnxruntime-web`. Raw shelf photos never leave the device, and no GPU server hours are required.

## 2. Live Shelf Scan, Count & Gap Overlay (60s)

1. Open the ShelfSense dashboard (dark blue-grey operations theme by default; click **Light** to show the light theme).
2. Select a **Store**, **Aisle**, and **Shelf** (e.g., *Dhaka Gulshan Superstore → Aisle 1 - Beverages → Shelf B2*).
3. Upload a shelf photo (or click **Load sample grocery shelf**).
4. Point out the two overlay layers:
   - **Sky-blue solid boxes:** every detected packaged item on the shelf.
   - **Amber dashed boxes with `-N` labels:** empty horizontal stock gaps computed from the median item width along each clustered shelf row.
5. Show the **Role** toggle:
   - As **Store Owner**, change the **Low-stock alert threshold** and watch the status badge flip between **Stock Normal** and **Low Stock Alert**.
   - Switch to **Aisle Staff**: the threshold input locks (`disabled`) while scanning remains enabled.

## 3. Scan History & CSV Export (30s)

1. Click **Save scan to history** to append the scan to the store's table.
2. Click **Export CSV** to download an RFC 4180 CSV (`shelfsense-scans.csv`) with formula-injection protection.

## 4. Bilingual Database-Tool Q&A in English and Bangla (60s)

1. In the **Inventory Q&A** box, ask:
   - `"Which shelf is lowest today?"`
   - `"Compare this week with last week"`
   - `"What is the stock count in our Chattogram branch?"` (demonstrates strict missing-data refusal — never invents numbers).
2. Click **বাংলা** in the top bar to switch the entire interface and numeral formatting into natural Bangla, then ask:
   - `"আজ কোন তাকে সবচেয়ে কম পণ্য আছে?"`
   - `"এই সপ্তাহের সাথে গত সপ্তাহের তুলনা করুন।"`
3. Point out the `[lowest_shelves]`, `[compare_periods]`, and `[refusal_missing_data]` tool badges verifying that every number comes from a database tool call.
