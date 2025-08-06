import requests
import json

# The base URL for your running FastAPI application
BASE_URL = "http://127.0.0.1:8000"

def print_response(title, response):
    """Helper function to print formatted JSON responses."""
    print(f"--- {title} ---")
    if response.status_code == 200:
        print(json.dumps(response.json(), indent=2))
    else:
        print(f"Error: {response.status_code}")
        try:
            print(json.dumps(response.json(), indent=2))
        except json.JSONDecodeError:
            print(response.text)
    print("-" * (len(title) + 8) + "\n")

def test_image_endpoint():
    """Tests the /analyse/image endpoint."""
    user_uuid = "a1b2c3d4-e5f6-7890-1234-567890abcdef"
    # A safe image
    safe_image_url = "https://www.sightengine.com/assets/img/examples/example-1-1-480.jpg"
    # An image that might be flagged
    flagged_image_url = "https://upload.wikimedia.org/wikipedia/commons/f/f0/Pro-Nudity_Rally.jpg"
    
    # Test safe image
    response_safe = requests.post(f"{BASE_URL}/analyse/image", json={"url": safe_image_url, "user_uuid": user_uuid})
    print_response("Image Analysis (Safe)", response_safe)
    
    # Test flagged image
    response_flagged = requests.post(f"{BASE_URL}/analyse/image", json={"url": flagged_image_url, "user_uuid": user_uuid})
    print_response("Image Analysis (Flagged)", response_flagged)

def test_video_endpoint():
    """Tests the /analyse/video endpoint."""
    user_uuid = "b2c3d4e5-f6a7-8901-2345-67890abcdef1"
    # NOTE: Replace with a valid, public video URL for testing.
    # Using a short, safe video is recommended.
    video_url = "https://cdn.discordapp.com/attachments/810439966215110696/1184823028882882600/screen-20231214-171318.mp4?ex=688ff42f&is=688ea2af&hm=00074ae8f2070fb9e7ec93489bca8f7573c4beb48aa84bacdb44948840edf5fa&"
    
    response = requests.post(f"{BASE_URL}/analyse/video", json={"url": video_url, "user_uuid": user_uuid})
    print_response("Video Analysis", response)

def test_text_endpoint():
    """Tests the /analyse/text endpoint."""
    user_uuid = "c3d4e5f6-a7b8-9012-3456-7890abcdef12"
    # Test 1: Harassment
    text_data_1 = {
        "text": "You are a complete idiot and nobody likes you.",
        "user_uuid": user_uuid,
        "thread_context": [
            "UserA: I think the new policy is a good idea.",
            "UserB: I disagree, it has some flaws."
        ]
    }
    response1 = requests.post(f"{BASE_URL}/analyse/text", json=text_data_1)
    print_response("Text Analysis (Harassment)", response1)

    # Test 2: Safe conversation
    text_data_2 = {
        "text": "Thanks for sharing your perspective!",
        "user_uuid": user_uuid,
        "thread_context": [
            "UserA: I think the new policy is a good idea.",
            "UserB: I disagree, it has some flaws."
        ]
    }
    response2 = requests.post(f"{BASE_URL}/analyse/text", json=text_data_2)
    print_response("Text Analysis (Safe)", response2)

if __name__ == "__main__":
    print("🚀 Starting API Endpoint Tests...")
    print("Make sure your FastAPI server is running: uvicorn api:app --reload")
    
    test_image_endpoint()
    test_video_endpoint()
    test_text_endpoint()
    
    print("✅ API Endpoint Tests Finished.")
