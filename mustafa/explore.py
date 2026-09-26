import pandas as pd, glob, json

ann = pd.read_csv("data/train/annotations.csv")
print(ann.head(10), "\n\nToplam kutu:", len(ann), "| Görsel:", ann.image_id.nunique())
print("\nSınıflar:\n", ann.label.value_counts())
print("\nAlan (w*h) istatistikleri:\n", (ann.w * ann.h).describe())
print("\nSample submission:\n", pd.read_csv("data/sample_submission.csv").head(5).to_string())
print("\nTest görsel:", len(glob.glob("data/test/images/*.jpg")))
print("\nSplit metadata:\n", json.dumps(json.load(open("splits/metadata.json")), indent=1)[:1500])