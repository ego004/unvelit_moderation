import requests
import json
import time

# API configuration
BASE_URL = "http://127.0.0.1:8000"
USER_UUID = "test-duplicate-user-123"

# Test URLs you provided
VIDEO_URL = "https://cdn.discordapp.com/attachments/810439966215110696/1184823028882882600/screen-20231214-171318.mp4?ex=6893e8af&is=6892972f&hm=d7e93dd032684f2dd0d9aae52a957c4d5d547c62fbbabee47c1d08bdf953761e&"
IMAGE_URL = "https://upload.wikimedia.org/wikipedia/commons/f/f0/Pro-Nudity_Rally.jpg"

def test_api_request(endpoint, data, test_name):
    """Make API request and print formatted response."""
    print(f"--- {test_name} ---")
    try:
        response = requests.post(f"{BASE_URL}/{endpoint}", json=data)
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Status: {response.status_code}")
            print(f"🔍 Is Duplicate: {result.get('is_duplicate', 'N/A')}")
            print(f"⚖️  Decision: {result.get('decision', 'N/A')}")
            print(f"📝 Reason: {result.get('reason', 'N/A')}")
            print(f"🆔 Request ID: {result.get('request_id', 'N/A')}")
            
            if result.get('similar_items'):
                print(f"🔗 Similar Items Found: {len(result['similar_items'])}")
                for i, item in enumerate(result['similar_items']):
                    print(f"   {i+1}. Similarity: {item.get('similarity', 'N/A')}")
                    
            return result
        else:
            print(f"❌ Error: {response.status_code}")
            try:
                error_detail = response.json()
                print(json.dumps(error_detail, indent=2))
            except:
                print(response.text)
            return None
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return None
    
    finally:
        print("-" * 50 + "\n")

def test_duplicate_detection():
    """Test duplicate detection by analyzing the same content multiple times."""
    
    print("🚀 Starting Duplicate Detection Test...")
    print("🎯 Testing with your provided URLs:")
    print(f"📷 Image: {IMAGE_URL}")
    print(f"🎬 Video: {VIDEO_URL}")
    print("Make sure your FastAPI server is running: uvicorn api:app --reload\n")
    
    print("📋 Test Plan:")
    print("1. Analyze image first time (should NOT be duplicate)")
    print("2. Analyze same image again (should BE duplicate)")
    print("3. Analyze video first time (should NOT be duplicate)")
    print("4. Analyze same video again (should BE duplicate)")
    print("5. Test batch processing with duplicate detection\n")
    
    # Test 1: First image analysis (should NOT be duplicate)
    image_data = {
        "url": IMAGE_URL,
        "user_uuid": USER_UUID
    }
    result1 = test_api_request("analyse/image", image_data, "Image Analysis - First Time")
    
    # Small delay to ensure different timestamps
    time.sleep(1)
    
    # Test 2: Same image analysis (should BE duplicate)
    result2 = test_api_request("analyse/image", image_data, "Image Analysis - Second Time (Should be Duplicate)")
    
    # Test 3: Same image analysis again (should BE duplicate)
    time.sleep(1)
    result3 = test_api_request("analyse/image", image_data, "Image Analysis - Third Time (Should be Duplicate)")
    
    # Test 4: First video analysis (should NOT be duplicate)
    video_data = {
        "url": VIDEO_URL,
        "user_uuid": USER_UUID
    }
    result4 = test_api_request("analyse/video", video_data, "Video Analysis - First Time")
    
    # Test 5: Same video analysis (should BE duplicate)
    time.sleep(1)
    result5 = test_api_request("analyse/video", video_data, "Video Analysis - Second Time (Should be Duplicate)")
    
    # Test 6: Batch processing with duplicates
    batch_data = {
        "images": [
            {"url": IMAGE_URL, "user_uuid": USER_UUID},
            {"url": IMAGE_URL, "user_uuid": USER_UUID},  # Same image again
            {"url": "https://upload.wikimedia.org/wikipedia/commons/4/47/PNG_transparency_demonstration_1.png", "user_uuid": USER_UUID}
        ],
        "max_concurrent": 3
    }
    result6 = test_api_request("analyse/images/batch", batch_data, "Batch Processing with Duplicates")
    
    print("🎯 Duplicate Detection Test Complete!")
    print("\n📊 Results Summary:")
    
    # Analyze results
    if result1:
        print(f"1. First image: is_duplicate = {result1.get('is_duplicate', 'ERROR')}")
    if result2:
        print(f"2. Second image: is_duplicate = {result2.get('is_duplicate', 'ERROR')}")
    if result3:
        print(f"3. Third image: is_duplicate = {result3.get('is_duplicate', 'ERROR')}")
    if result4:
        print(f"4. First video: is_duplicate = {result4.get('is_duplicate', 'ERROR')}")
    if result5:
        print(f"5. Second video: is_duplicate = {result5.get('is_duplicate', 'ERROR')}")
    
    print("\n🔍 Expected Results:")
    print("- First analysis of each content: is_duplicate = false")
    print("- Subsequent same content: is_duplicate = true")
    print("- All duplicate requests should skip external API calls")
    print("- Performance should be significantly faster for duplicates")
    
    print("\n💡 Notes:")
    print("- If you see all 'false' for is_duplicate, the database might need to be cleared")
    print("- If you see API errors, check your SightEngine API credentials")
    print("- Video processing may take longer due to frame extraction")

if __name__ == "__main__":
    test_duplicate_detection()
