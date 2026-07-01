import os

path = "/mnt/ssd/pvrolo-data/repos/fantasma/api/.env"
print("=== .env KEYS (sin exponer valores) ===")
try:
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            status = f"SET (len={len(val)})" if val else "EMPTY"
            print(f"{key}: {status}")
except Exception as e:
    print("ERROR reading .env:", e)

print("=== os.getenv visibilidad en runtime ===")
for k in ["FRED_API_KEY", "BANXICO_TOKEN", "BANXICO_API_KEY", "SIE_TOKEN"]:
    v = os.getenv(k, "")
    print(f"{k}: {'SET' if v else 'EMPTY/UNSET'}")
