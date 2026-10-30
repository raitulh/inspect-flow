# Dataset layout

Use a legally collected, consented and representative factory dataset. Keep camera/site/customer identifiers out of filenames and metadata where practical.

```text
lineguard-dataset/
  data.yaml
  images/
    train/
    val/
    test/        # optional held-out final test split
  labels/
    train/
    val/
    test/        # optional
```

Labels use YOLO detection format: `class_id x_center y_center width height`, with coordinates normalized to `[0,1]`. Empty label text files represent images with no target objects. Split by production run / date / physical unit, not randomly adjacent frames, to reduce leakage. Keep the final test set untouched until model selection is complete.

Suggested class list is a starting point only. Define defect taxonomy with process/quality engineers. Include good parts, normal variation, lighting changes, motion blur, occlusion, multiple SKUs and difficult negatives. Do not use internet images as a substitute for target-line validation.
