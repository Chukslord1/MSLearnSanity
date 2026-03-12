import os
import sys
import requests
import re

SIGHTENGINE_USER = os.getenv("SIGHTENGINE_USER")
SIGHTENGINE_SECRET = os.getenv("SIGHTENGINE_SECRET")
GOOGLE_VISION_KEY = os.getenv("GOOGLE_VISION_KEY")

AI_THRESHOLD = 0.85
PLAGIARISM_THRESHOLD = 1


# ===== GET CHANGED IMAGES =====
def get_changed_images():
    changed = os.getenv("CHANGED_FILES", "")
    files = changed.splitlines()

    images = [
        f.strip()
        for f in files
        if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
    ]

    return images


# ===== SANITIZE NAME (must match GitHub Action) =====
def sanitize_filename(name):
    return re.sub(r'[^a-zA-Z0-9]', '_', name)


# ===== GET IMAGE URL FROM ENV =====
def get_image_url(image_path):

    filename = os.path.basename(image_path)

    safe_name = sanitize_filename(filename)

    env_name = f"IMAGE_URL_{safe_name}"

    url = os.getenv(env_name)

    if not url:
        print(f"⚠️ No public URL found for {image_path}")
        return None

    return url


# ===== GOOGLE VISION REVERSE IMAGE SEARCH =====
def check_plagiarism(image_path):

    image_url = get_image_url(image_path)

    if not image_url:
        return False

    try:

        response = requests.post(
            f"https://vision.googleapis.com/v1/images:annotate?key={GOOGLE_VISION_KEY}",
            json={
                "requests": [
                    {
                        "image": {"source": {"imageUri": image_url}},
                        "features": [{"type": "WEB_DETECTION"}]
                    }
                ]
            },
            timeout=30
        )

        if response.status_code != 200:
            print("⚠️ Google Vision request failed:", response.text)
            return False

        data = response.json()

        web = data["responses"][0].get("webDetection", {})

        matches = web.get("pagesWithMatchingImages", [])

        print(f"🔎 Matching pages found: {len(matches)}")

        return len(matches) >= PLAGIARISM_THRESHOLD

    except Exception as e:
        print(f"⚠️ Plagiarism check failed: {e}")
        return False


# ===== AI DETECTION =====
def check_ai(image_path):

    if not os.path.isfile(image_path):
        print(f"⚠️ File not found: {image_path}")
        return 0

    if not SIGHTENGINE_USER or not SIGHTENGINE_SECRET:
        print("⚠️ Sightengine credentials missing.")
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

        if response.status_code != 200:
            print("⚠️ Sightengine request failed:", response.text)
            return 0

        data = response.json()

        # Debug print (helps verify API works)
        print("Sightengine response:", data)

        genai = data.get("genai", {})

        prob = genai.get("prob", 0)

        return prob

    except Exception as e:
        print(f"⚠️ AI detection failed: {e}")
        return 0
        

# ===== MAIN =====
def main():

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

        # plagiarism detection
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
