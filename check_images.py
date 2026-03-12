import os
import sys
import requests
import re
import openai

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SIGHTENGINE_USER = os.getenv("SIGHTENGINE_USER")
SIGHTENGINE_SECRET = os.getenv("SIGHTENGINE_SECRET")
GOOGLE_VISION_KEY = os.getenv("GOOGLE_VISION_KEY")

AI_THRESHOLD = 0.85
PLAGIARISM_THRESHOLD = 1
openai.api_key = OPENAI_API_KEY


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




# ===== AI DETECTION =====# ===== AI DETECTION =====
def check_ai(image_path):
    if not os.path.isfile(image_path):
        print(f"⚠️ File not found: {image_path}")
        return 0

    if not OPENAI_API_KEY:
        print("⚠️ OpenAI API key missing.")
        return 0

    try:
        # Read image bytes
        with open(image_path, "rb") as f:
            image_bytes = f.read()

        # Encode as base64
        import base64
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        # Prompt GPT-4o with the image
        prompt = (
            "You are an AI detection assistant.\n"
            "Check if the following image is AI-generated.\n"
            "Reply with a number between 0 and 1 indicating the probability it's AI-generated.\n\n"
            f"data:image/png;base64,{image_b64}"
        )

        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )

        result_text = response.choices[0].message.content.strip()
        print("OpenAI AI detection response:", result_text)

        # Extract numeric probability
        match = re.search(r"([0-1](?:\.\d+)?)", result_text)
        ai_prob = float(match.group(1)) if match else 0

        return ai_prob

    except Exception as e:
        print(f"⚠️ AI detection via OpenAI failed: {e}")
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
