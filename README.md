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
Treat `val.txt` and every `fold_*_val.txt` manifest as validation-only; never
include those image IDs in the corresponding training run.
They contain image IDs without file extensions. The split uses seed 42 and
reserves 20% of images for validation. It is
stratified by the complete set of classes present in each image, including
background-only images. `splits/metadata.json` records the source annotation
checksum so teammates can confirm that they have the same dataset version.

Treat these manifests as the team's common benchmark. Change them only when the
team agrees to adopt a new split.

For five-fold cross-validation, use the paired train/validation manifests in
`splits/folds/`. Across the five folds, every image is used for validation
exactly once. See `splits/folds/metadata.json` for counts and the dataset
checksum.

For future model selection, prefer
`splits/scene_holdout_v1/{train,val}.txt`. Use its `val.txt` for validation
only. This fixed split keeps visually similar same-resolution scene groups on
one side of the split and matches the unlabeled test set's resolution and
brightness distributions while preserving class, density, and object-scale
balance. `groups.csv` records each image's atomic scene group, and
`metadata.json` documents the construction and audit. The original random
split and five folds remain available for comparison with earlier pilots.

## Collaboration

Each teammate and their coding agents must work only inside that teammate's
personal folder.

Every agent must add a very short summary of its work and primary result to
`collective_summary.txt`. Read that file first and do not redo work already
completed by another agent.

Pull before starting work, and commit, push, and pull frequently so every agent
stays up to date.

Create a short-lived branch for each experiment, keep configuration changes
with the corresponding code, and merge into `main` through pull requests. Do
not commit datasets, model weights, predictions, or secrets.
