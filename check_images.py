import os
import sys
import requests
from base64 import b64encode

# ====== CONFIG ======
SIGHTENGINE_USER = os.getenv("SIGHTENGINE_USER")
SIGHTENGINE_SECRET = os.getenv("SIGHTENGINE_SECRET")
IMAGGA_KEY = os.getenv("IMAGGA_KEY")
IMAGGA_SECRET = os.getenv("IMAGGA_SECRET")

AI_THRESHOLD = 0.85
PLAGIARISM_THRESHOLD = 1  # minimal number of similar images to flag


# ====== GET CHANGED IMAGES ======
def get_changed_images():
    changed = os.getenv("CHANGED_FILES", "")
    files = changed.splitlines()
    images = [
        f.strip() for f in files if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
    ]
    return images


# ====== IMAGGA REVERSE IMAGE SEARCH ======
def check_plagiarism(image_path):
    if not os.path.isfile(image_path):
        print(f"⚠️ File not found for plagiarism check: {image_path}")
        return False

    try:
        with open(image_path, "rb") as f:
            encoded_image = b64encode(f.read()).decode("utf-8")

        auth = (IMAGGA_KEY, IMAGGA_SECRET)
        response = requests.post(
            "https://api.imagga.com/v2/similar_images",
            auth=auth,
            files={"image": (os.path.basename(image_path), open(image_path, "rb"))},
            timeout=30
        )

        if response.status_code != 200:
            print("⚠️ Imagga request failed:", response.text)
            return False

        data = response.json()
        similar_images = data.get("result", {}).get("similar_images", [])

        print(f"🔎 Candidate URLs found: {len(similar_images)}")
        return len(similar_images) >= PLAGIARISM_THRESHOLD

    except Exception as e:
        print(f"⚠️ Plagiarism check failed: {e}")
        return False


# ====== AI DETECTION (Sightengine) ======
def check_ai(image_path):
    if not os.path.isfile(image_path):
        print(f"⚠️ File not found for AI check: {image_path}")
        return 0

    try:
        with open(image_path, "rb") as img:
            response = requests.post(
                "https://api.sightengine.com/1.0/check.json",
                files={"media": img},
                data={
                    "models": "genai",
                    "api_user": SIGHTENGINE_USER,
                    "api_secret": SIGHTENGINE_SECRET
                },
                timeout=30
            )

        data = response.json()
        return data.get("genai", {}).get("prob", 0)

    except Exception as e:
        print(f"⚠️ AI detection failed: {e}")
        return 0


# ====== MAIN ======
def main():
    if not (IMAGGA_KEY and IMAGGA_SECRET):
        print("❌ IMAGGA_KEY or IMAGGA_SECRET not found in environment.")
        sys.exit(1)

    images = get_changed_images()
    if not images:
        print("No new images found in this PR.")
        return

    failed = False

    for img in images:
        print(f"\n🔍 Checking {img}...")
        if not os.path.isfile(img):
            print(f"⚠️ Skipping missing file: {img}")
            continue

        # AI detection
        ai_prob = check_ai(img)
        print(f"🤖 AI probability: {ai_prob}")
        if ai_prob >= AI_THRESHOLD:
            print(f"❌ {img} appears AI-generated.")
            failed = True

        # Plagiarism detection
        plag = check_plagiarism(img)
        if plag:
            print(f"❌ {img} appears to exist elsewhere online.")
            failed = True

    if failed:
        print("\n❌ Image validation failed.")
        sys.exit(1)

    print("\n✅ All images passed AI and plagiarism checks.")


if __name__ == "__main__":
    main()
