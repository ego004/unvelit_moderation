import os
from dotenv import load_dotenv  # Import dotenv
from database.main import MySQLClient
from image.main import ImageAnalysis
from video.main import VideoAnalysis
from text.main import TextAnalysis

load_dotenv()  # Load .env into environment

def main():
    # Configure database connection (replace with your credentials)
    db = MySQLClient(
        host=os.getenv('DB_HOST', 'localhost'),
        user=os.getenv('DB_USER', 'root'),
        password=os.getenv('DB_PASS', ''),
        database=os.getenv('DB_NAME', 'unvelit')
    )
    db.connect()

    # Example Image Analysis
    image_path = 'https://upload.wikimedia.org/wikipedia/commons/f/f0/Pro-Nudity_Rally.jpg'  # update with real path
    image_analyzer = ImageAnalysis(image_path)
    img_result = image_analyzer.analyse(
        db_connection=db,
        similarity_threshold=8,
        table_name='images',
        save_to_db=True
    )
    print('Image Analysis Result:', img_result)

    print()

    # Example Video Analysis
    video_path = 'https://cdn.discordapp.com/attachments/810439966215110696/1184823028882882600/screen-20231214-171318.mp4?ex=688ff42f&is=688ea2af&hm=00074ae8f2070fb9e7ec93489bca8f7573c4beb48aa84bacdb44948840edf5fa&'
    print("🎬 Starting Video Analysis...")
    video_analyzer = VideoAnalysis(video_path)
    vid_result = video_analyzer.analyse(
        db_connection=db,
        similarity_threshold=8,
        table_name='videos',
        save_to_db=True
    )
    print('Video Analysis Result:', vid_result)

    print()

    # Example Text Analysis
    thread_context = [
        "UserA: Just saw the new movie, it was awesome!",
        "UserB: I agree, the special effects were incredible."
    ]
    new_message = "UserC: That's a stupid opinion. Anyone who liked that movie is an idiot."
    
    print("📝 Starting Text Analysis...")
    text_analyzer = TextAnalysis(new_message, thread_context)
    text_result = text_analyzer.analyse(db_connection=db)
    print('Text Analysis Result:', text_result)

    db.close()

if __name__ == '__main__':
    main()
