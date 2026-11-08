import sys, time, json
from PIL import Image
from app.kyc.parse import parse_document
for name in sys.argv[1:]:
    t = time.time()
    r = parse_document(Image.open(f"../data/kyc_documents/{name}.png"))
    print(name, r["doc_type"], round(time.time()-t,1), "s", json.dumps(r["fields"], ensure_ascii=False), r["corrections"] or "")
