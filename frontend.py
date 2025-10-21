"""
Streamlit Frontend for Course Summarizer & Quiz Generator
"""

import streamlit as st
import requests
import json
from typing import Dict, List, Optional
import time
import re

# Configure page
st.set_page_config(
    page_title="Course Summarizer & Quiz Generator",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# API configuration
API_BASE_URL = "http://localhost:8000"

def check_api_health() -> bool:
    """Check if the FastAPI backend is running"""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        return response.status_code == 200
    except:
        return False

def process_course(content: str = None, title: Optional[str] = None, video_url: Optional[str] = None) -> Optional[str]:
    """Start course processing and return task_id"""
    try:
        payload = {}
        if content:
            payload["content"] = content
        if title:
            payload["title"] = title
        if video_url:
            payload["video_url"] = video_url

        # Start processing
        response = requests.post(
            f"{API_BASE_URL}/process_course",
            json=payload,
            timeout=30  # Shorter timeout since it's just starting the task
        )

        if response.status_code == 200:
            data = response.json()
            return data.get("task_id")
        else:
            st.error(f"API Error: {response.status_code} - {response.text}")
            return None

    except requests.exceptions.RequestException as e:
        st.error(f"Connection Error: {str(e)}")
        return None

def get_result(task_id: str) -> Optional[Dict]:
    """Get the result of a completed task"""
    try:
        response = requests.get(f"{API_BASE_URL}/result/{task_id}", timeout=30)
        if response.status_code == 200:
            data = response.json()
            # Check if it's still processing
            if "status" in data and data["status"] == "processing":
                return None
            return data
        else:
            return None
    except:
        return None

def poll_progress(task_id: str) -> Dict:
    """Poll for processing progress"""
    try:
        response = requests.get(f"{API_BASE_URL}/progress/{task_id}", timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            return {"stage": "error", "progress": 0.0, "message": "Failed to get progress"}
    except:
        return {"stage": "error", "progress": 0.0, "message": "Connection failed"}

def display_summary(summary: str):
    """Display the course summary"""
    st.subheader("📝 Course Summary")
    st.write(summary)

def display_learning_objectives(objectives: List[str]):
    """Display learning objectives"""
    st.subheader("🎯 Learning Objectives")
    for i, objective in enumerate(objectives, 1):
        st.write(f"{i}. {objective}")

def display_quiz(quiz: List[Dict]):
    """Display quiz questions with interactive answers"""
    st.subheader("🧠 Quiz")

    if not quiz:
        st.write("No quiz questions generated.")
        return

    for i, question in enumerate(quiz, 1):
        st.markdown(f"**Question {i}:** {question['question']}")

        # Create radio buttons for options
        options = question['options']
        key = f"q_{i}"

        # Get current selection from session state or default to None
        current_selection = st.session_state.get(key, None)

        # Remove duplicate options
        unique_options = []
        for opt in options:
            if opt not in unique_options:
                unique_options.append(opt)

        selected = st.radio(
            f"Select your answer for Question {i}:",
            unique_options,
            key=key,
            index=unique_options.index(current_selection) if current_selection in unique_options else None,
            label_visibility="collapsed"
        )

        # Show feedback immediately if answered
        if selected:
            correct = question['correct'].strip()
            selected_stripped = selected.strip()
            is_correct = selected_stripped == correct

            if is_correct:
                st.success("✅ Correct!")
            else:
                st.error(f"❌ Incorrect. The correct answer is: {correct}")

            with st.expander("Show Explanation"):
                st.write(question.get('explanation', 'No explanation provided.'))

        st.markdown("---")        # Optional: Show quiz completion status
    answered_keys = [f"q_{i+1}" for i in range(len(quiz))]
    answered_count = sum(1 for key in answered_keys if st.session_state.get(key))
    if answered_count == len(quiz):
        st.success(f"🎉 Quiz completed! You answered {answered_count}/{len(quiz)} questions.")
    else:
        st.info(f"📊 Progress: {answered_count}/{len(quiz)} questions answered")

def display_glossary(glossary: Dict[str, str]):
    """Display the glossary"""
    st.subheader("📖 Glossary")

    if not glossary:
        st.write("No glossary terms generated.")
        return

    # Create two columns for better layout
    col1, col2 = st.columns(2)

    terms = list(glossary.items())
    mid_point = len(terms) // 2

    with col1:
        for term, definition in terms[:mid_point]:
            with st.expander(f"**{term}**"):
                st.write(definition)

    with col2:
        for term, definition in terms[mid_point:]:
            with st.expander(f"**{term}**"):
                st.write(definition)

def main():
    """Main Streamlit application"""

    # Title and description
    st.title("📚 Course Summarizer & Quiz Generator")
    st.markdown("""
    Transform your course materials into comprehensive summaries, learning objectives, quizzes, and glossaries
    using our multi-agent AI pipeline.
    """)

    # Check if we have results in session state
    if 'processing_results' in st.session_state and st.session_state.processing_results:
        # Display existing results
        result = st.session_state.processing_results
        source_type = result.get("source_type", "text")

        st.success(f"✅ Course processed successfully from {source_type} source!")

        # Navigation between different result views
        view_options = ["📝 Summary", "🎯 Objectives", "🧠 Quiz", "📖 Glossary"]
        if 'current_view' not in st.session_state:
            st.session_state.current_view = "📝 Summary"

        # View selector
        current_view = st.selectbox(
            "Select view:",
            view_options,
            index=view_options.index(st.session_state.current_view),
            key="view_selector"
        )

        # Update session state when view changes
        st.session_state.current_view = current_view

        # Display the selected view
        if current_view == "📝 Summary":
            display_summary(result.get("summary", ""))
        elif current_view == "🎯 Objectives":
            display_learning_objectives(result.get("learning_objectives", []))
        elif current_view == "🧠 Quiz":
            display_quiz(result.get("quiz", []))
        elif current_view == "📖 Glossary":
            display_glossary(result.get("glossary", {}))

        # Show processing time and source
        processing_time = result.get('processing_time', 0)
        st.info(f"⏱️ Processing time: {processing_time:.2f} seconds | 📊 Source: {source_type}")

        # Button to process new course
        if st.button("🔄 Process New Course"):
            st.session_state.processing_results = None
            if 'current_view' in st.session_state:
                del st.session_state.current_view
            st.rerun()

        return

    # Sidebar
    with st.sidebar:
        st.header("⚙️ Settings")

        # API Health Check
        if check_api_health():
            st.success("✅ API Connected")
        else:
            st.error("❌ API Not Connected")
            st.info("Make sure the FastAPI backend is running on localhost:8000")

        st.markdown("---")

        # About section
        st.markdown("""
        **Powered by:**
        - LangChain + Google Gemini
        - Multi-agent AI pipeline
        - FastAPI backend
        """)

    # Main content
    tab1, tab2 = st.tabs(["📤 Process Course", "ℹ️ About"])

    with tab1:
        st.header("Upload Course Material")

        # Input method selection
        input_method = st.radio(
            "Choose input method:",
            ["Text Input", "File Upload", "Video URL"],
            horizontal=True
        )

        content = ""
        title = ""
        video_url = ""

        if input_method == "Text Input":
            title = st.text_input("Course Title (optional)", placeholder="Enter course title...")
            content = st.text_area(
                "Course Content",
                height=300,
                placeholder="Paste your course material here..."
            )

        elif input_method == "File Upload":
            uploaded_file = st.file_uploader(
                "Upload course material file",
                type=['txt', 'md', 'pdf'],
                help="Supported formats: TXT, MD, PDF"
            )

            if uploaded_file:
                # For now, handle text files. PDF would need additional processing
                if uploaded_file.type == "text/plain":
                    content = uploaded_file.read().decode("utf-8")
                    title = uploaded_file.name
                elif uploaded_file.type == "text/markdown":
                    content = uploaded_file.read().decode("utf-8")
                    title = uploaded_file.name
                else:
                    st.error("PDF files are not yet supported. Please paste the content as text.")

        else:  # Video URL
            st.info("🎥 Support for YouTube, Vimeo, and other video platforms")
            st.warning("⚠️ Note: Some videos may fail to download due to platform restrictions. If processing fails, try a different video or paste the transcript directly as text.")
            video_url = st.text_input(
                "Video URL",
                placeholder="https://www.youtube.com/watch?v=... or https://vimeo.com/..."
            )
            title = st.text_input("Course Title (optional)", placeholder="Enter course title...")

            if video_url:
                # Basic URL validation
                import re
                url_pattern = re.compile(
                    r'https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/|vimeo\.com/|dailymotion\.com/video/|twitch\.tv/videos/)[^\s&]+'
                )
                if not url_pattern.match(video_url):
                    st.warning("⚠️ Please enter a valid video URL from supported platforms (YouTube, Vimeo, Dailymotion, Twitch)")

        # Process button
        if st.button("🚀 Process Course", type="primary", use_container_width=True):
            # Validation
            if input_method == "Video URL" and not video_url.strip():
                st.error("Please provide a video URL.")
                return
            elif input_method != "Video URL" and not content.strip():
                st.error("Please provide course content.")
                return

            if not check_api_health():
                st.error("Cannot connect to the API. Please make sure the backend is running.")
                return

            with st.spinner("🤖 Processing course material with AI agents..."):
                progress_bar = st.progress(0)
                status_text = st.empty()

                # Start processing
                task_id = process_course(content=content if input_method != "Video URL" else None,
                                       title=title,
                                       video_url=video_url if input_method == "Video URL" else None)

                if not task_id:
                    st.error("Failed to start processing.")
                    return

                # Poll for progress
                while True:
                    progress_data = poll_progress(task_id)
                    stage = progress_data.get("stage", "unknown")
                    progress = progress_data.get("progress", 0.0)
                    message = progress_data.get("message", "")

                    progress_bar.progress(progress)
                    status_text.text(message)

                    if stage in ["complete", "error"] or progress >= 1.0:
                        break

                    time.sleep(1)  # Poll every second

                if stage == "error":
                    progress_bar.empty()
                    status_text.empty()
                    st.error(f"Processing failed: {message}")
                    return

                # Get final result - poll until available
                result = None
                for _ in range(10):  # Try up to 10 times
                    result = get_result(task_id)
                    if result:
                        break
                    time.sleep(1)

                if result:
                    progress_bar.progress(1.0)
                    status_text.text("✅ Processing completed successfully!")
                    source_type = result.get("source_type", "text")
                    st.success(f"✅ Course processed successfully from {source_type} source!")

                    # Store results in session state to persist across reruns
                    st.session_state.processing_results = result
                    st.session_state.current_view = "📝 Summary"  # Start with summary view

                    # Navigation between different result views
                    view_options = ["📝 Summary", "🎯 Objectives", "🧠 Quiz", "📖 Glossary"]
                    current_view = st.selectbox(
                        "Select view:",
                        view_options,
                        index=0,  # Start with Summary
                        key="initial_view_selector"
                    )

                    # Update session state when view changes
                    st.session_state.current_view = current_view

                    # Display the selected view
                    if current_view == "📝 Summary":
                        display_summary(result.get("summary", ""))
                    elif current_view == "🎯 Objectives":
                        display_learning_objectives(result.get("learning_objectives", []))
                    elif current_view == "🧠 Quiz":
                        display_quiz(result.get("quiz", []))
                    elif current_view == "📖 Glossary":
                        display_glossary(result.get("glossary", {}))

                    # Show processing time and source
                    processing_time = result.get('processing_time', 0)
                    st.info(f"⏱️ Processing time: {processing_time:.2f} seconds | 📊 Source: {source_type}")

                else:
                    progress_bar.empty()
                    status_text.empty()
                    st.error("Failed to get processing results. Please try again.")

    with tab2:
        st.header("About This Application")

        st.markdown("""
        ### 🎯 What it does
        This application uses a sophisticated multi-agent AI system to automatically:

        - **Process Videos**: Extract transcripts from YouTube, Vimeo, and other video platforms (currently using mock transcription for testing)
        - **Summarize** long-form course materials into concise, readable summaries
        - **Extract** key learning objectives from the content
        - **Generate** interactive multiple-choice quizzes with explanations
        - **Create** technical glossaries with definitions

        ### 🤖 How it works
        The system employs four specialized AI agents working in parallel:

        1. **Planner Agent**: Analyzes content and creates processing strategy
        2. **Summarizer Agent**: Generates comprehensive course summaries
        3. **Quiz Generator Agent**: Creates challenging multiple-choice questions
        4. **Reviewer Agent**: Validates output quality and provides feedback

        ### ⚡ Performance Features
        - **Asynchronous processing** for faster results
        - **Token optimization** to reduce API costs
        - **Containerized deployment** for easy scaling

        ### 🛠️ Technology Stack
        - **Frontend**: Streamlit (Python web app framework)
        - **Backend**: FastAPI (high-performance async web framework)
        - **AI**: Google Gemini 1.5 Pro via LangChain
        - **Deployment**: Docker & Docker Compose

        ### 🚀 Getting Started
        1. Make sure the FastAPI backend is running (`python main.py`)
        2. Install Streamlit: `pip install streamlit`
        3. Run this app: `streamlit run frontend.py`
        4. Open your browser to the provided URL

        ### 📊 API Usage
        The frontend communicates with a REST API that provides:
        - Course processing endpoint
        - Health check monitoring
        - Automatic API documentation at `/docs`
        """)

if __name__ == "__main__":
    main()