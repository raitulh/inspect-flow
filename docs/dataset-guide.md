# Dataset collection and labeling guide

## Choose a narrow task

Start with a single clearly specified condition at one station, such as presence of a known component in a fixed region. Do not label vague categories such as "bad assembly" without a written definition and examples.

## Record provenance

For each collection, record station, camera ID, camera angle, lens/focus, image resolution, lighting conditions, shift or date window, part/SKU variation, source owner, permission and retention policy. Do not include secrets in filenames or dataset paths.

## Suggested manifest format

```json
{
  "dataset_name": "assembly-station-01",
  "dataset_version": "0.1.0",
  "license_or_permission": "document exact internal authorization",
  "label_schema_version": "1",
  "records": [
    {
      "asset": "images/frame-0001.jpg",
      "split": "train",
      "label": "component_present",
      "station": "ASSY-01",
      "annotation_note": "clear view, normal lighting"
    }
  ]
}
```

Use relative paths in the manifest. Store no personal identifiers in file metadata unless necessary and approved.

## Labels

- Define each class precisely.
- Establish rules for partly occluded, borderline, damaged, unknown or out-of-scope examples.
- Have a second reviewer inspect a sample of labels.
- Record disagreements and resolve them before reporting performance.
- For detection models, annotate bounding boxes/masks consistently. For image classification, use one label per frame only when a frame-level label is appropriate.

## Splits and evaluation

- Split by collection session, production batch, day or camera condition rather than randomly distributing adjacent frames; near-duplicate frames can inflate results.
- Keep a frozen test set untouched during model and threshold tuning.
- Document class imbalance and sample counts.
- Report per-class precision, recall and false positives/misses alongside totals.
- Preserve representative hard negatives (reflections, empty stations, visually similar parts, partial visibility and changing lighting).

## Privacy and governance

Get authorization for recording and processing factory footage. Minimize capture of people, restrict evidence access, avoid facial recognition, and implement an explicit retention policy. Respect product confidentiality, supplier restrictions and dataset licenses.
