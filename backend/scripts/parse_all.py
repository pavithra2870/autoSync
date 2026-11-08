"""Dev helper: parse all 47 specimen documents and print the extracted fields."""
import glob, os, sys, time, json
from PIL import Image
from app.kyc.parse import parse_document
t = time.time()
for f in sorted(glob.glob("../data/kyc_documents/*.png")):
    r = parse_document(Image.open(f))
    flds = {k: v for k, v in r["fields"].items() if k not in ("gstin_raw", "udyam_raw")}
    print(os.path.basename(f)[:-4], r["doc_type"], "BLURRY" if r["blurry"] else "", json.dumps(flds, ensure_ascii=False), r["corrections"] or "")
print("total secs", round(time.time() - t, 1))
