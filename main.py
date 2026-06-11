"""
Course Summarizer & Quiz Generator
Multi-agent AI pipeline using LangChain and Gemini
"""

import asyncio
import os
import tempfile
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
import json
from datetime import datetime
from dotenv import load_dotenv
import hashlib
import yt_dlp
import whisper
import ffmpeg
import redis
import re

# Load environment variables from .env file
load_dotenv()

# Simple cache for loaded Whisper models to avoid repeated heavy loads
_WHISPER_MODELS = {}

def get_whisper_model(name: str = "base"):
    """Return a cached Whisper model, loading it on first use.

    Keeps memory/IO overhead lower when transcribing multiple files.
    """
    global _WHISPER_MODELS
    if name in _WHISPER_MODELS:
        return _WHISPER_MODELS[name]
    model = whisper.load_model(name)
    _WHISPER_MODELS[name] = model
    return model

# Global progress tracking
progress_store = {}
result_store = {}

def parse_json_response(response: str):
    """Parse JSON from AI response, handling cases where response contains extra text"""
    try:
        # Try direct parsing first
        return json.loads(response.strip())
    except json.JSONDecodeError:
        # Try to find JSON in the response using regex
        json_match = re.search(r'\{.*\}|\[.*\]', response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        # If still fails, try to clean the response
        cleaned = response.strip()
        if cleaned.startswith('```json'):
            cleaned = cleaned[7:]
        if cleaned.endswith('```'):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            raise ValueError(f"Could not parse JSON from response: {response[:200]}...")

def update_progress(task_id: str, stage: str, progress: float, message: str = ""):
    """Update progress for a task"""
    if task_id not in progress_store:
        progress_store[task_id] = {}
    progress_store[task_id].update({
        "stage": stage,
        "progress": progress,
        "message": message,
        "timestamp": datetime.now().isoformat()
    })

async def process_course_background(content: str, title: Optional[str], video_url: Optional[str], task_id: str):
    """Background task for processing course"""
    try:
        print(f"Starting background processing for task {task_id}")
        result = await process_course_async(content, title, video_url, task_id)
        # Store the result in result_store for retrieval
        result_store[task_id] = result
        update_progress(task_id, "complete", 1.0, "Processing completed successfully!")
        print(f"Background processing completed for task {task_id}")
    except Exception as e:
        print(f"Background processing failed for task {task_id}: {str(e)}")
        update_progress(task_id, "error", 0.0, f"Processing failed: {str(e)}")

# Initialize FastAPI app
app = FastAPI(
    title="Course Summarizer & Quiz Generator",
    description="Multi-agent AI pipeline for course material processing",
    version="1.0.0"
)

# Initialize Redis for caching (optional)
redis_available = False
redis_client = None
try:
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    redis_client = redis.from_url(redis_url)
    redis_client.ping()
    redis_available = True
    print("✅ Redis connected")
except Exception as e:
    print(f"⚠️ Redis not available: {e}")
    redis_client = None

# Initialize OpenRouter models
llm_primary = ChatOpenAI(
    model="nvidia/nemotron-3-super-120b-a12b:free",
    temperature=0.3,
    openai_api_key=os.getenv("OPENROUTER_KEY"),
    openai_api_base="https://openrouter.ai/api/v1"
)

llm_secondary = ChatOpenAI(
    model="google/gemma-4-31b-it:free",
    temperature=0.3,
    openai_api_key=os.getenv("OPENROUTER_KEY"),
    openai_api_base="https://openrouter.ai/api/v1"
)

llm_tertiary = ChatOpenAI(
    model="openai/gpt-oss-20b:free",
    temperature=0.3,
    openai_api_key=os.getenv("OPENROUTER_KEY"),
    openai_api_base="https://openrouter.ai/api/v1"
)

# Pydantic models
class CourseRequest(BaseModel):
    content: Optional[str] = None
    title: Optional[str] = None
    video_url: Optional[str] = None

class CourseResponse(BaseModel):
    summary: str
    learning_objectives: List[str]
    quiz: List[Dict]
    glossary: Dict[str, str]
    processing_time: float
    source_type: str  # "text" or "video"
    task_id: str  # Add task_id to response

# Agent prompts
PLANNER_PROMPT = """You are a Course Planning Agent. Analyze the course material and create a processing plan.

Course Content: {content}

Create a structured plan for:
1. Key topics to extract
2. Learning objectives to identify
3. Quiz question types needed
4. Glossary terms to define

Return ONLY a valid JSON object with keys: topics (array), objectives (array), quiz_types (array), glossary_terms (array).

Example: {{"topics": ["topic1", "topic2"], "objectives": ["obj1", "obj2"], "quiz_types": ["multiple-choice"], "glossary_terms": ["term1", "term2"]}}"""

SUMMARIZER_PROMPT = """You are a Course Summarization Agent. Create a concise but comprehensive summary.

Course Content: {content}
Key Topics: {topics}

Generate a well-structured summary that covers all important concepts while being concise."""

QUIZ_GENERATOR_PROMPT = """You are a Quiz Generation Agent. Create multiple-choice questions.

Course Content: {content}
Learning Objectives: {objectives}
Quiz Types: {quiz_types}
Number of Questions: {num_questions}

Generate {num_questions} multiple-choice questions with 4 textual options each. Each option should be a complete, meaningful answer choice, not just letters.

Return ONLY a valid JSON array with this exact format:
[{{"question": "Question text here?", "options": ["Complete option text 1", "Complete option text 2", "Complete option text 3", "Complete option text 4"], "correct": "Complete option text 1", "explanation": "Explanation here"}}]

Do not include any other text or formatting."""

REVIEWER_PROMPT = """You are a Quality Review Agent. Review and improve the generated content.

Summary: {summary}
Quiz: {quiz}
Glossary: {glossary}

Check for:
1. Summary completeness and clarity
2. Quiz question quality and accuracy
3. Glossary term relevance and definitions

Return improved versions if needed, or confirm quality is good."""

GLOSSARY_PROMPT = """You are a Glossary Generation Agent. Create a technical glossary.

Course Content: {content}
Key Terms: {terms}

Extract and define 10-15 key technical terms with clear, concise definitions.

Return ONLY a valid JSON object with term-definition pairs.

Example: {{"term1": "definition1", "term2": "definition2"}}"""

# Agent functions
async def planner_agent(content: str) -> Dict:
    """Plan the course processing strategy"""
    prompt = ChatPromptTemplate.from_template(PLANNER_PROMPT)
    chain = prompt | llm_primary | StrOutputParser()

    result = await chain.ainvoke({"content": content})
    try:
        return parse_json_response(result)
    except:
        # Fallback plan
        return {
            "topics": ["course content analysis"],
            "objectives": ["understand key concepts"],
            "quiz_types": ["multiple-choice"],
            "glossary_terms": ["key terms"]
        }

async def summarizer_agent(content: str, topics: List[str]) -> str:
    """Generate course summary"""
    prompt = ChatPromptTemplate.from_template(SUMMARIZER_PROMPT)
    chain = prompt | llm_secondary | StrOutputParser()

    return await chain.ainvoke({
        "content": content,
        "topics": ", ".join(topics)
    })

async def quiz_generator_agent(content: str, objectives: List[str], quiz_types: List[str]) -> List[Dict]:
    """Generate quiz questions"""
    # Calculate number of questions based on content length
    content_length = len(content)
    if content_length < 1000:
        num_questions = 3
    elif content_length < 5000:
        num_questions = 5
    else:
        num_questions = min(8, max(3, content_length // 1000))  # Scale with content but cap at 8

    prompt = ChatPromptTemplate.from_template(QUIZ_GENERATOR_PROMPT)
    chain = prompt | llm_tertiary | StrOutputParser()

    result = await chain.ainvoke({
        "content": content,
        "objectives": ", ".join(objectives),
        "quiz_types": ", ".join(quiz_types),
        "num_questions": num_questions
    })

    try:
        return parse_json_response(result)
    except:
        # Fallback quiz
        return [{
            "question": "What is the main topic of this course?",
            "options": ["Topic A", "Topic B", "Topic C", "Topic D"],
            "correct": "Topic A",
            "explanation": "Based on the course content"
        }]

async def glossary_agent(content: str, terms: List[str]) -> Dict[str, str]:
    """Generate glossary"""
    prompt = ChatPromptTemplate.from_template(GLOSSARY_PROMPT)
    chain = prompt | llm_primary | StrOutputParser()

    result = await chain.ainvoke({
        "content": content,
        "terms": ", ".join(terms)
    })

    try:
        return parse_json_response(result)
    except:
        # Fallback glossary
        return {"term": "definition"}

async def reviewer_agent(summary: str, quiz: List[Dict], glossary: Dict[str, str]) -> Dict:
    """Review and validate output quality"""
    prompt = ChatPromptTemplate.from_template(REVIEWER_PROMPT)
    chain = prompt | llm_secondary | StrOutputParser()

    result = await chain.ainvoke({
        "summary": summary,
        "quiz": json.dumps(quiz),
        "glossary": json.dumps(glossary)
    })

    return {"review": result, "approved": True}

# Video processing functions
def extract_youtube_video_id(url: str) -> Optional[str]:
    """Extract the video ID from a YouTube URL"""
    patterns = [
        r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/watch\?v=([a-zA-Z0-9_-]{11})',
        r'(?:https?:\/\/)?(?:www\.)?youtu\.be\/([a-zA-Z0-9_-]{11})',
        r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/embed\/([a-zA-Z0-9_-]{11})',
        r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/v\/([a-zA-Z0-9_-]{11})',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

async def process_video_content(video_url: str, task_id: str = None) -> str:
    """Process video URL and extract transcript with progress tracking"""
    # First, try to fetch YouTube captions directly
    video_id = extract_youtube_video_id(video_url)
    if video_id:
        try:
            if task_id:
                update_progress(task_id, "downloading", 0.1, " Fetching YouTube captions directly...")
            print(f" Attempting to fetch YouTube captions for video ID: {video_id}")
            from youtube_transcript_api import YouTubeTranscriptApi
            ytt_api = YouTubeTranscriptApi()
            fetched_transcript = await asyncio.get_event_loop().run_in_executor(
                None, ytt_api.fetch, video_id
            )
            # Combine transcript text
            transcript = " ".join([snippet.text for snippet in fetched_transcript])
            print(f" Captions fetched successfully: {len(transcript)} characters")
            if task_id:
                update_progress(task_id, "transcribing", 0.9, " Captions fetched successfully")
            return transcript
        except Exception as e:
            print(f" Could not fetch direct captions: {str(e)}. Falling back to audio transcription.")
            if task_id:
                update_progress(task_id, "downloading", 0.1, " Direct captions failed, falling back to audio download...")

    # Use a persistent temp file
    import uuid
    temp_audio_path = f"temp_audio_{uuid.uuid4().hex}.m4a"

    try:
        print(f" Processing video audio fallback: {video_url}")

        # Step 1: Download audio
        if task_id:
            update_progress(task_id, "downloading", 0.1, " Downloading video audio...")
        print(" Downloading audio...")
        audio_path = await asyncio.get_event_loop().run_in_executor(
            None, download_video_audio_persistent, video_url, temp_audio_path
        )
        print(f" Audio downloaded: {os.path.getsize(audio_path)} bytes")
        if task_id:
            update_progress(task_id, "downloading", 0.3, " Audio downloaded successfully")

        # Step 2: Transcribe audio (this is the longest step)
        if task_id:
            update_progress(task_id, "transcribing", 0.4, " Transcribing speech to text...")
        print(" Transcribing audio with Whisper... (this may take several minutes)")
        transcript = await asyncio.get_event_loop().run_in_executor(
            None, transcribe_audio, audio_path
        )
        print(f" Transcription completed: {len(transcript)} characters")
        if task_id:
            update_progress(task_id, "transcribing", 0.9, " Transcription completed")

        return transcript

    except Exception as e:
        # Clean up temp file
        try:
            if os.path.exists(temp_audio_path):
                os.remove(temp_audio_path)
        except:
            pass
        if task_id:
            update_progress(task_id, "error", 0.0, f"❌ Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Video processing failed: {str(e)}")
    finally:
        # Clean up temp file
        try:
            if os.path.exists(temp_audio_path):
                os.remove(temp_audio_path)
        except:
            pass

def download_video_audio_persistent(video_url: str, output_path: str) -> str:
    """Download audio from video URL to a persistent file"""
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': output_path,
        'quiet': True,
        'no_warnings': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-us,en;q=0.5',
            'Sec-Fetch-Mode': 'navigate',
        },
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web'],
            }
        },
        'no_check_certificate': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])

        if os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            if file_size < 1000:
                raise Exception(f"Downloaded file too small: {file_size} bytes")
            return output_path
        else:
            raise Exception("Download completed but file not found")

    except Exception as e:
        raise Exception(f"Failed to download audio: {str(e)}")

def transcribe_audio(audio_path: str) -> str:
    """Transcribe audio file to text using Whisper"""
    print(f"Starting transcription of: {audio_path}")
    print(f"File exists: {os.path.exists(audio_path)}")

    if not os.path.exists(audio_path):
        raise Exception(f"Audio file not found: {audio_path}")

    file_size = os.path.getsize(audio_path)
    print(f"File size: {file_size} bytes")

    try:
        # Load Whisper model (cached for performance)
        model = get_whisper_model("base")
        result = model.transcribe(audio_path, fp16=False)  # Disable fp16 for CPU
        transcript = result["text"].strip()

        if not transcript:
            raise Exception("Transcription returned empty text")

        print(f"Transcription completed: {len(transcript)} characters")
        return transcript

    except Exception as e:
        print(f"Whisper transcription failed: {e}")
        # Try with tiny model as fallback
        try:
            print("Trying with tiny model...")
            model = get_whisper_model("tiny")
            result = model.transcribe(audio_path, fp16=False)
            transcript = result["text"].strip()

            if transcript:
                print(f"Tiny model transcription completed: {len(transcript)} characters")
                return transcript
        except Exception as e2:
            print(f"Tiny model also failed: {e2}")

        # Final fallback
        raise Exception(f"All transcription attempts failed. Original error: {str(e)}")

async def run_with_retry(func, *args, **kwargs):
    """Simple retry wrapper with backoff for rate limits"""
    for attempt in range(6):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            if "429" in str(e) or "rate" in str(e).lower() or attempt == 5:
                if attempt == 5:
                    raise
                wait_time = 15 * (attempt + 1)
                print(f" Upstream rate limit hit! Retrying in {wait_time}s... (Attempt {attempt+1}/5)")
                await asyncio.sleep(wait_time)
            else:
                raise e

# Main processing pipeline
async def process_course_async(content: str, title: Optional[str] = None, video_url: Optional[str] = None, task_id: str = None) -> Dict:
    """Asynchronous course processing pipeline with caching"""

    # Handle video URL if provided
    source_type = "text"
    if video_url:
        if task_id:
            update_progress(task_id, "analyzing", 0.0, " Analyzing video URL...")
        content = await process_video_content(video_url, task_id)
        source_type = "video"

    if task_id:
        update_progress(task_id, "planning", 0.1, " Planning course structure...")

    # Check cache if Redis is available
    content_bytes = (content or "").encode("utf-8")
    cache_key = f"course:{hashlib.sha256(content_bytes).hexdigest()}"
    cached_result = None
    if redis_available and redis_client:
        try:
            cached_result = redis_client.get(cache_key)
            if cached_result:
                cached_data = json.loads(cached_result)
                cached_data["source_type"] = source_type
                if task_id:
                    update_progress(task_id, "complete", 1.0, " Processing completed (from cache)")
                return cached_data
        except Exception as e:
            print(f"Redis cache read error: {e}")

    start_time = datetime.now()

    # Execute agents asynchronously
    plan_task = asyncio.create_task(run_with_retry(planner_agent, content))

    # Wait for planner
    plan = await plan_task
    if task_id:
        update_progress(task_id, "planning", 0.2, " Course structure planned")

    # Execute agents sequentially to avoid bursting the API rate limits (429 errors)
    if task_id:
        update_progress(task_id, "processing", 0.3, " Generating summary...")
    summary = await run_with_retry(summarizer_agent, content, plan.get("topics", []))
    
    if task_id:
        update_progress(task_id, "processing", 0.5, " Generating quiz...")
    quiz = await run_with_retry(
        quiz_generator_agent,
        content,
        plan.get("objectives", []),
        plan.get("quiz_types", [])
    )
    
    if task_id:
        update_progress(task_id, "processing", 0.7, " Extracting glossary...")
    glossary = await run_with_retry(glossary_agent, content, plan.get("glossary_terms", []))

    if task_id:
        update_progress(task_id, "processing", 0.8, " AI agents completed")

    # Review results
    if task_id:
        update_progress(task_id, "reviewing", 0.9, " Reviewing quality...")
    review = await run_with_retry(reviewer_agent, summary, quiz, glossary)

    processing_time = (datetime.now() - start_time).total_seconds()

    result = {
        "summary": summary,
        "learning_objectives": plan.get("objectives", []),
        "quiz": quiz,
        "glossary": glossary,
        "processing_time": processing_time,
        "source_type": source_type,
        "review": review
    }

    # Cache result if Redis is available
    if redis_available and redis_client:
        try:
            redis_client.setex(cache_key, 3600, json.dumps(result))  # Cache for 1 hour
        except Exception as e:
            print(f"Redis cache write error: {e}")

    if task_id:
        update_progress(task_id, "complete", 1.0, " Processing completed successfully")

    return result

# API endpoints
@app.post("/process_course")
async def process_course(request: CourseRequest, background_tasks: BackgroundTasks):
    """Process course material through multi-agent pipeline"""

    # Validate input
    if not request.content and not request.video_url:
        raise HTTPException(status_code=400, detail="Either content or video_url must be provided")

    if request.content and request.video_url:
        raise HTTPException(status_code=400, detail="Provide either content OR video_url, not both")

    if not os.getenv("OPENROUTER_KEY"):
        raise HTTPException(status_code=500, detail="OpenRouter API key not configured")

    # Generate task ID for progress tracking
    import uuid
    task_id = str(uuid.uuid4())

    # Initialize progress
    update_progress(task_id, "starting", 0.0, " Starting processing...")

    # Start background processing
    background_tasks.add_task(
        process_course_background,
        request.content,
        request.title,
        request.video_url,
        task_id
    )

    return {"task_id": task_id, "status": "processing", "message": "Processing started"}

@app.get("/result/{task_id}")
async def get_result(task_id: str):
    """Get the result of a completed task"""
    if task_id in result_store:
        result = result_store[task_id]
        return CourseResponse(
            summary=result["summary"],
            learning_objectives=result["learning_objectives"],
            quiz=result["quiz"],
            glossary=result["glossary"],
            processing_time=result["processing_time"],
            source_type=result["source_type"],
            task_id=task_id
        )
    elif task_id in progress_store:
        progress_info = progress_store[task_id]
        if progress_info.get("stage") == "complete":
            # Task completed but no result stored - this shouldn't happen
            return {"status": "error", "message": "Processing completed but result not found", "progress_info": progress_info}
        else:
            # Return current progress info
            return {"status": "processing", "progress": progress_info}
    else:
        raise HTTPException(status_code=404, detail="Task not found")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/progress/{task_id}")
async def get_progress(task_id: str):
    """Get progress for a task"""
    if task_id in progress_store:
        return progress_store[task_id]
    else:
        return {"stage": "not_found", "progress": 0.0, "message": "Task not found", "timestamp": datetime.now().isoformat()}

@app.get("/debug/progress")
async def debug_progress():
    """Debug endpoint to check progress store"""
    return progress_store

@app.get("/debug/results")
async def debug_results():
    """Debug endpoint to check result store"""
    return result_store

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Course Summarizer & Quiz Generator API",
        "version": "1.0.0",
        "docs": "/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)