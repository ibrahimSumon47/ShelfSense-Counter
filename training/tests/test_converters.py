"""Unit tests for SKU-110K CSV, Supervisely JSON, VOC XML, YOLO, and COCO converters."""
from pathlib import Path
import json

from shelfsense_training.converters import (
    compute_density_summary,
    export_coco_dict,
    format_yolo_lines,
    parse_sku110k_csv,
    parse_supervisely_annotation,
    parse_voc_xml,
    write_coco_json,
    write_yolo_dataset,
)


def test_parse_sku110k_csv_clamps_and_drops_degenerate_boxes() -> None:
    """Valid rows are parsed and clamped; degenerate or negative-size boxes are ignored."""
    csv_sample = "\n".join(
        [
            "train_0.jpg,10,20,110,220,object,1000,1000",
            "train_0.jpg,-5,50,95,150,object,1000,1000",
            "train_0.jpg,200,200,200,250,object,1000,1000",  # zero width -> dropped
            "train_1.jpg,0,0,500,500,object,500,500",
        ]
    )
    records = parse_sku110k_csv(csv_sample)
    assert len(records) == 2
    r0 = records[0]
    assert r0.image_name == "train_0.jpg"
    assert len(r0.boxes) == 2
    assert r0.boxes[1].x1 == 0.0  # clamped from -5


def test_parse_supervisely_filters_out_price_tags() -> None:
    """Supervisely parser keeps 'Product' boxes and excludes 'Price' tags."""
    payload = {
        "size": {"width": 2000, "height": 1000},
        "objects": [
            {"classTitle": "Product", "points": {"exterior": [[100, 100], [300, 400]]}},
            {"classTitle": "Price", "points": {"exterior": [[120, 410], [280, 450]]}},
            {"classTitle": "product", "points": {"exterior": [[400, 100], [600, 400]]}},
        ],
    }
    rec = parse_supervisely_annotation("shelf_01.jpg", payload)
    assert rec.width == 2000
    assert rec.height == 1000
    assert len(rec.boxes) == 2


def test_parse_voc_xml_and_export_yolo_and_coco(tmp_path: Path) -> None:
    """VOC XML converts cleanly into both normalized YOLO .txt and COCO .json."""
    xml_data = """
    <annotation>
      <filename>aisle_1.jpg</filename>
      <size><width>1000</width><height>500</height></size>
      <object>
        <name>Product</name>
        <bndbox><xmin>100</xmin><ymin>50</ymin><xmax>300</xmax><ymax>250</ymax></bndbox>
      </object>
      <object>
        <name>Price</name>
        <bndbox><xmin>100</xmin><ymin>260</ymin><xmax>200</xmax><ymax>290</ymax></bndbox>
      </object>
    </annotation>
    """
    rec = parse_voc_xml(xml_data)
    assert len(rec.boxes) == 1
    lines = format_yolo_lines(rec)
    assert lines == ["0 0.200000 0.300000 0.200000 0.400000"]

    labels_dir = tmp_path / "labels"
    assert write_yolo_dataset([rec], labels_dir) == 1
    assert (labels_dir / "aisle_1.txt").read_text(encoding="utf-8").strip() == lines[0]

    coco_path = tmp_path / "annotations.json"
    write_coco_json([rec], coco_path)
    coco = json.loads(coco_path.read_text(encoding="utf-8"))
    assert len(coco["images"]) == 1
    assert len(coco["annotations"]) == 1
    assert coco["annotations"][0]["bbox"] == [100.0, 50.0, 200.0, 200.0]

    summary = compute_density_summary([rec])
    assert summary["images"] == 1
    assert summary["total_boxes"] == 1
    assert export_coco_dict([rec])["categories"][0]["name"] == "item"
