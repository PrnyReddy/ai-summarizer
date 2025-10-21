#!/usr/bin/env python3
"""
Enable real Whisper transcription by uncommenting the code in main.py
"""

def enable_real_transcription():
    """Uncomment the real Whisper transcription code"""

    # Read the main.py file
    with open('main.py', 'r', encoding='utf-8') as f:
        content = f.read()

    # Replace the mock transcription with real Whisper code
    old_code = '''    try:
        # For now, return mock transcript for testing
        # TODO: Implement real Whisper transcription
        mock_transcript = """
        This is a sample course video transcript. In this video, we will learn about artificial intelligence and machine learning.
        The course covers fundamental concepts including neural networks, deep learning, and natural language processing.
        Students will learn how to build AI models, train them on data, and deploy them in production environments.
        Key topics include supervised learning, unsupervised learning, reinforcement learning, and computer vision.
        By the end of this course, participants will have hands-on experience with popular AI frameworks and tools.
        """

        print("Using mock transcript for testing (Whisper integration pending)")
        return mock_transcript.strip()

        # Uncomment below for real Whisper transcription when ffmpeg issues are resolved
        # model = whisper.load_model("base")
        # result = model.transcribe(audio_path, fp16=False)  # Disable fp16 for CPU
        # return result["text"]'''

    new_code = '''    try:
        # Real Whisper transcription
        model = whisper.load_model("base")
        result = model.transcribe(audio_path, fp16=False)  # Disable fp16 for CPU
        return result["text"]'''

    if old_code in content:
        content = content.replace(old_code, new_code)
        with open('main.py', 'w', encoding='utf-8') as f:
            f.write(content)
        print("✅ Real Whisper transcription enabled!")
        print("Make sure FFmpeg is properly installed and in your PATH.")
        return True
    else:
        print("❌ Could not find the mock transcription code to replace")
        return False

if __name__ == "__main__":
    enable_real_transcription()