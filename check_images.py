import os
import sys
import requests

COPYSEEKER_KEY = os.getenv("COPYSEEKER_KEY")
SIGHTENGINE_USER = os.getenv("SIGHTENGINE_USER")
SIGHTENGINE_SECRET = os.getenv("SIGHTENGINE_SECRET")

AI_THRESHOLD = 0.85
PLAGIARISM_THRESHOLD = 1  # fail if at least 1 match


# ====== GET CHANGED IMAGES ======
def get_changed_images():
    changed = os.getenv("CHANGED_FILES", "")

    # GitHub action outputs files separated by spaces
    files = changed.split()

    images = [
        f.strip()
        for f in files
        if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
    ]

    return images


# ====== COPYSEEKER REVERSE IMAGE SEARCH ======
def check_plagiarism(image_path):
    url = "https://reverse-image-search-by-copyseeker.p.rapidapi.com/"

    headers = {
        "X-RapidAPI-Key": COPYSEEKER_KEY,
        "X-RapidAPI-Host": "reverse-image-search-by-copyseeker.p.rapidapi.com"
    }

    with open(image_path, "rb") as img:
        files = {"image": img}

        response = requests.post(
            url,
            headers=headers,
            files=files
        )

    if response.status_code != 200:
        print("⚠️ Copyseeker request failed:", response.text)
        return False

    data = response.json()

    # handle multiple possible response formats
    matches = (
        data.get("results", [])
        or data.get("similar_images", [])
        or data.get("matches", [])
    )

    print(f"🔎 Reverse image matches found: {len(matches)}")

    return len(matches) >= PLAGIARISM_THRESHOLD


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

    prob = data.get("genai", {}).get("prob", 0)

    return prob


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
