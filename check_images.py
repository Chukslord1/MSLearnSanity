import os
import sys
import requests

ZEN_API_KEY = os.getenv("ZEN_API_KEY")
SIGHTENGINE_USER = os.getenv("SIGHTENGINE_USER")
SIGHTENGINE_SECRET = os.getenv("SIGHTENGINE_SECRET")
AI_THRESHOLD = 0.85

# ====== GET CHANGED IMAGES ======
def get_changed_images():
    changed = os.getenv("CHANGED_FILES", "")
    files = changed.split(",") if changed else []
    images = [f.strip() for f in files if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))]
    return images

# ====== PLAGIARISM CHECK (Zenserp) ======
def check_plagiarism(image_path):
    IMAGE_URL = os.getenv("IMAGE_URL_" + os.path.basename(image_path))
    if not IMAGE_URL:
        print(f"⚠️ No public URL found for {image_path}, skipping Zenserp check.")
        return False

    response = requests.get(
        "https://app.zenserp.com/api/v2/search",
        params={
            "apikey": ZEN_API_KEY,
            "search_type": "images",
            "image_url": IMAGE_URL
        }
    )

    data = response.json()
    if "image_results" in data and len(data["image_results"]) > 0:
        return True
    return False

# ====== AI DETECTION (Sightengine) ======
def check_ai(image_path):
    with open(image_path, "rb") as img:
        response = requests.post(
            "https://api.sightengine.com/1.0/check.json",
            files={"media": img},
            data={
                "models": "genai",
                "api_user": SIGHTENGINE_USER,
                "api_secret": SIGHTENGINE_SECRET
            }
        )
    data = response.json()
    return data.get("genai", {}).get("prob", 0)

# ====== MAIN ======
def main():
    images = get_changed_images()
    if not images:
        print("No new images found in this PR.")
        return

    failed = False
    for img in images:
        print(f"\nChecking {img}...")

        ai_prob = check_ai(img)
        print(f"AI probability: {ai_prob}")
        if ai_prob >= AI_THRESHOLD:
            print(f"❌ {img} appears AI-generated.")
            failed = True

        plag = check_plagiarism(img)
        if plag:
            print(f"⚠️ {img} might be plagiarized online.")
            failed = True

    if failed:
        sys.exit(1)

if __name__ == "__main__":
    main()
