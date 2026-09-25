# Roketsan Hackathon — Vehicle Detection

Collaborative object-detection project for detecting buses, cars, trucks, and
vans in images.

## Local data

Raw data is intentionally excluded from Git. Place the competition data in the
following layout:

```text
data/
├── train/
│   ├── annotations.csv
│   └── images/*.jpg
├── test/images/*.jpg
└── sample_submission.csv
```

The expected annotation columns are `image_id,x,y,w,h,label`.

## Shared split

The committed manifests in `splits/` define the shared train/validation split.
They contain image IDs without file extensions. The split uses seed 42 and
reserves 20% of images for validation. It is
stratified by the complete set of classes present in each image, including
background-only images. `splits/metadata.json` records the source annotation
checksum so teammates can confirm that they have the same dataset version.

Treat these manifests as the team's common benchmark. Change them only when the
team agrees to adopt a new split.

## Collaboration

Create a short-lived branch for each experiment, keep configuration changes
with the corresponding code, and merge into `main` through pull requests. Do
not commit datasets, model weights, predictions, or secrets.
