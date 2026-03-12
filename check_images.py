import os
import sys
import requests

COPYSEEKER_KEY = os.getenv("COPYSEEKER_KEY")
SIGHTENGINE_USER = os.getenv("SIGHTENGINE_USER")
SIGHTENGINE_SECRET = os.getenv("SIGHTENGINE_SECRET")

AI_THRESHOLD = 0.85
PLAGIARISM_THRESHOLD = 1


# ====== GET CHANGED IMAGES ======
def get_changed_images():
    changed = os.getenv("CHANGED_FILES", "")

    # Use newline split (safe for filenames with spaces/parentheses)
    files = changed.splitlines()

    images = [
        f.strip()
        for f in files
        if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
    ]

    return images


# ====== COPYSEEKER REVERSE IMAGE SEARCH ======
def check_plagiarism(image_path):

    image_url = os.getenv("IMAGE_URL_" + os.path.basename(image_path))

    if not image_url:
        print(f"⚠️ No public URL for {image_path}, skipping plagiarism check.")
        return False

    headers = {
        "X-RapidAPI-Key": COPYSEEKER_KEY,
        "X-RapidAPI-Host": "reverse-image-search-by-copyseeker.p.rapidapi.com"
    }

    with open(image_path, "rb") as f:
        response = requests.post(
            "https://reverse-image-search-by-copyseeker.p.rapidapi.com/",
            headers=headers,
            files={"image": f},
            timeout=30
        )
    
    except Exception as e:
        print(f"⚠️ Copyseeker request failed: {e}")
        return False

    if response.status_code != 200:
        print("⚠️ Copyseeker request failed:", response.text)
        return False

    data = response.json()

    candidate_urls = (
        data.get("results", [])
        or data.get("similar_images", [])
        or data.get("matches", [])
        or []
    )

    print(f"🔎 Candidate URLs found: {len(candidate_urls)}")

    return len(candidate_urls) >= PLAGIARISM_THRESHOLD


# ====== AI DETECTION (Sightengine) ======
def check_ai(image_path):

    if not os.path.exists(image_path):
        print(f"⚠️ File not found: {image_path}")
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

    if not COPYSEEKER_KEY:
        print("❌ COPYSEEKER_KEY not found in environment.")
        sys.exit(1)

    images = get_changed_images()

    if not images:
        print("No new images found in this PR.")
        return

    failed = False

    for img in images:

        print(f"\n🔍 Checking {img}...")

        if not os.path.exists(img):
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
