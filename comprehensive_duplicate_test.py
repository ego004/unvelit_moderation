import requests
import json
import time

# API configuration
BASE_URL = "http://127.0.0.1:8000"
USER_UUID = "test-duplicate-user-123"

# Test URLs you provided
VIDEO_URL = "https://cdn.discordapp.com/attachments/810439966215110696/1184823028882882600/screen-20231214-171318.mp4?ex=6893e8af&is=6892972f&hm=d7e93dd032684f2dd0d9aae52a957c4d5d547c62fbbabee47c1d08bdf953761e&"
IMAGE_URL = "https://upload.wikimedia.org/wikipedia/commons/f/f0/Pro-Nudity_Rally.jpg"

def clear_database_via_api():
    """Clear database using the API endpoint."""
    print("🗑️  Clearing database via API...")
    try:
        response = requests.post(f"{BASE_URL}/debug/clear-database")
        if response.status_code == 200:
            result = response.json()
            print(f"✅ {result['message']}")
            return True
        else:
            print(f"❌ Failed to clear database: {response.status_code}")
            print(response.text)
            return False
    except Exception as e:
        print(f"❌ Error clearing database: {e}")
        return False

def test_api_request(endpoint, data, test_name):
    """Make API request and print formatted response."""
    print(f"--- {test_name} ---")
    try:
        start_time = time.time()
        response = requests.post(f"{BASE_URL}/{endpoint}", json=data)
        end_time = time.time()
        response_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Status: {response.status_code} | ⏱️  Response Time: {response_time}ms")
            print(f"🔍 Is Duplicate: {result.get('is_duplicate', 'N/A')}")
            print(f"⚖️  Decision: {result.get('decision', 'N/A')}")
            print(f"📝 Reason: {result.get('reason', 'N/A')}")
            print(f"🆔 Request ID: {result.get('request_id', 'N/A')}")
            
            if result.get('similar_items'):
                print(f"🔗 Similar Items Found: {len(result['similar_items'])}")
                for i, item in enumerate(result['similar_items']):
                    print(f"   {i+1}. URL: {item.get('url', 'N/A')[:50]}...")
                    print(f"      Similarity: {item.get('similarity', 'N/A')}")
                    
            return result
        else:
            print(f"❌ Error: {response.status_code} | ⏱️  Response Time: {response_time}ms")
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
        print("-" * 60 + "\n")

def comprehensive_duplicate_test():
    """Comprehensive test of duplicate detection functionality."""
    
    print("🚀 COMPREHENSIVE DUPLICATE DETECTION TEST")
    print("=" * 60)
    print(f"📷 Image URL: {IMAGE_URL}")
    print(f"🎬 Video URL: {VIDEO_URL}")
    print("Make sure your FastAPI server is running: uvicorn api:app --reload\n")
    
    # Step 1: Clear database
    if not clear_database_via_api():
        print("⚠️  Database clearing failed, but continuing with test...")
    
    print("\n📋 TEST PLAN:")
    print("1. Clear database to ensure clean state")
    print("2. Analyze image first time → should NOT be duplicate")
    print("3. Analyze same image again → should BE duplicate")
    print("4. Analyze video first time → should NOT be duplicate") 
    print("5. Analyze same video again → should BE duplicate")
    print("6. Test performance difference between first and duplicate requests")
    print("=" * 60 + "\n")
    
    # Image Tests
    print("🖼️  IMAGE DUPLICATE DETECTION TESTS")
    print("-" * 40)
    
    image_data = {
        "url": IMAGE_URL,
        "user_uuid": USER_UUID
    }
    
    # Test 1: First image analysis
    result1 = test_api_request("analyse/image", image_data, "Image Test 1: First Analysis")
    time.sleep(1)  # Small delay
    
    # Test 2: Same image (should be duplicate)
    result2 = test_api_request("analyse/image", image_data, "Image Test 2: Second Analysis (Should be Duplicate)")
    time.sleep(1)
    
    # Test 3: Same image again (should be duplicate)
    result3 = test_api_request("analyse/image", image_data, "Image Test 3: Third Analysis (Should be Duplicate)")
    
    # Video Tests
    print("🎬 VIDEO DUPLICATE DETECTION TESTS")
    print("-" * 40)
    
    video_data = {
        "url": VIDEO_URL,
        "user_uuid": USER_UUID
    }
    
    # Test 4: First video analysis
    result4 = test_api_request("analyse/video", video_data, "Video Test 1: First Analysis")
    time.sleep(1)
    
    # Test 5: Same video (should be duplicate)
    result5 = test_api_request("analyse/video", video_data, "Video Test 2: Second Analysis (Should be Duplicate)")
    
    # Results Analysis
    print("📊 RESULTS ANALYSIS")
    print("=" * 60)
    
    def analyze_result(test_name, result, expected_duplicate):
        if result:
            actual_duplicate = result.get('is_duplicate', False)
            status = "✅ PASS" if actual_duplicate == expected_duplicate else "❌ FAIL"
            print(f"{status} {test_name}")
            print(f"   Expected duplicate: {expected_duplicate}")
            print(f"   Actual duplicate: {actual_duplicate}")
            print(f"   Decision: {result.get('decision', 'N/A')}")
            print(f"   Reason: {result.get('reason', 'N/A')}")
        else:
            print(f"❌ FAIL {test_name} - No result received")
        print()
    
    analyze_result("Image Test 1 (First)", result1, False)
    analyze_result("Image Test 2 (Second)", result2, True)
    analyze_result("Image Test 3 (Third)", result3, True)
    analyze_result("Video Test 1 (First)", result4, False)
    analyze_result("Video Test 2 (Second)", result5, True)
    
    print("🎯 SUMMARY")
    print("-" * 30)
    print("Expected Behavior:")
    print("• First analysis of new content: is_duplicate = false")
    print("• Subsequent analyses of same content: is_duplicate = true")
    print("• Duplicates should have faster response times")
    print("• Duplicates should skip external API calls")
    
    print("\nIf duplicate detection isn't working:")
    print("• Check database connection and credentials")
    print("• Verify hash calculation is consistent")
    print("• Check similarity threshold settings")
    print("• Ensure database tables have proper indexes")

if __name__ == "__main__":
    comprehensive_duplicate_test()
