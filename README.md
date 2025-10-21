# Course Summarizer & Quiz Generator

A multi-agent AI pipeline that automatically processes videos and text to generate comprehensive course materials, summaries, learning objectives, quizzes, and glossaries.

## Features

- **Multi-Agent Architecture**: Specialized agents for planning, summarization, quiz generation, and review
- **Asynchronous Processing**: Parallel agent execution for improved performance
- **Context Caching**: Redis-based caching to reduce latency and API costs
- **Video Processing**: Extract transcripts from YouTube, Vimeo, and other video platforms (currently using mock transcription)
- **FastAPI Microservice**: RESTful API with automatic documentation
- **Streamlit Frontend**: User-friendly web interface for easy interaction
- **Containerized Deployment**: Docker support for easy deployment

## Architecture

The system uses a LangChain orchestration with four specialized agents:

1. **Planner Agent**: Analyzes course material and creates processing strategy
2. **Summarizer Agent**: Generates concise course summaries
3. **Quiz Generator Agent**: Creates multiple-choice questions with explanations
4. **Reviewer Agent**: Validates output quality and provides feedback

## Setup

### Prerequisites

- Python 3.9+
- Google Gemini API key
- Redis server

### Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd coursesummary
   ```

2. Create virtual environment:
   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   ```bash
   # Copy the example environment file
   cp .env.example .env
   ```

5. Start Redis server (if not already running)

## Docker Deployment

### Prerequisites

- Docker and Docker Compose installed
- Gemini API key

### Quick Start with Docker

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd coursesummary
   ```

2. Set up environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your Google Gemini API key
   ```

3. Start all services:
   ```bash
   docker-compose up -d
   ```

4. Access the application:
   - Frontend: http://localhost:8501
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs

### Docker Services

- **backend**: FastAPI service with video processing capabilities
- **frontend**: Streamlit web interface
- **redis**: Redis cache for performance optimization

### Docker Commands

```bash
# Start services in background
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Rebuild and restart
docker-compose up --build -d

# Scale services (if needed)
docker-compose up -d --scale backend=2
```

### Production Deployment

For production deployment:

1. Update `.env` with production values
2. Use Redis Cloud or managed Redis service
3. Configure proper domain and SSL certificates
4. Set up monitoring and logging

## Usage

### Option 1: Streamlit Web Interface (Recommended)

1. Start the FastAPI backend:
   ```bash
   python main.py
   ```

2. In a new terminal, start the Streamlit frontend:
   ```bash
   streamlit run frontend.py
   ```

3. Open your browser to the Streamlit URL (usually `http://localhost:8501`)

### Option 2: API Only

```bash
python main.py
```

The API will be available at `http://127.0.0.1:8000`

### API Documentation

Visit `http://127.0.0.1:8000/docs` for interactive API documentation.

### Example Request

```bash
# Text content
curl -X POST "http://127.0.0.1:8000/process_course" \
     -H "Content-Type: application/json" \
     -d '{
       "content": "Your course material text here...",
       "title": "Optional Course Title"
     }'

# Video URL
curl -X POST "http://127.0.0.1:8000/process_course" \
     -H "Content-Type: application/json" \
     -d '{
       "video_url": "https://www.youtube.com/watch?v=VIDEO_ID",
       "title": "Optional Course Title"
     }'
```

### Example Response

```json
{
  "summary": "Comprehensive course summary...",
  "learning_objectives": [
    "Understand key concepts",
    "Apply learned principles"
  ],
  "quiz": [
    {
      "question": "What is the main concept?",
      "options": ["A", "B", "C", "D"],
      "correct": "A",
      "explanation": "Explanation of the correct answer"
    }
  ],
  "glossary": {
    "term1": "definition1",
    "term2": "definition2"
  },
  "processing_time": 2.34
}
```

## Video Processing

The application supports processing video content from YouTube, Vimeo, and other platforms:

### Current Implementation
- ✅ Video download using yt-dlp
- ✅ Audio extraction from video
- ⚠️ **Mock transcription** (returns sample text for testing)
- ✅ Full AI pipeline processing of transcripts

### To Enable Real Transcription

1. **Install FFmpeg properly** (ensure it's in system PATH)
2. **Run the enable script**:
   ```bash
   python enable_whisper.py
   ```
3. **Test with real videos**

The video processing pipeline:
1. Downloads video audio using yt-dlp
2. Extracts audio track
3. Transcribes audio to text using OpenAI Whisper
4. Processes transcript through AI agents
5. Returns summary, quiz, and glossary

### Supported Video Platforms
- YouTube
- Vimeo
- Dailymotion
- Twitch VODs
- Any yt-dlp supported platform

## Performance Optimizations

- **Asynchronous Execution**: Agents run in parallel to reduce total processing time
- **Redis Caching**: Results cached for 1 hour to avoid redundant processing
- **Token Optimization**: Efficient prompts minimize API usage
- **Connection Pooling**: Redis connection reuse for better performance

## Configuration

Create a `.env` file in the project root with the following variables:

```bash
# Google Gemini API Key (Required)
GOOGLE_API_KEY=your_api_key_here

# Redis Configuration (Optional - defaults provided)
REDIS_URL=redis://redis:6379  # For Docker deployment
# REDIS_URL=redis://localhost:6379  # For local development
# REDIS_URL=redis://username:password@your-redis-cloud-url:port  # For Redis Cloud

# Service Configuration (Optional)
BACKEND_PORT=8000
FRONTEND_PORT=8501
```

### Environment Variables

- `GOOGLE_API_KEY`: Required. Your Google Gemini API key
- `REDIS_URL`: Redis connection URL (default: redis://redis:6379 for Docker, redis://localhost:6379 for local)
- `BACKEND_PORT`: FastAPI backend port (default: 8000)
- `FRONTEND_PORT`: Streamlit frontend port (default: 8501)

## Development

### Running Tests

```bash
pytest
```

### Code Formatting

```bash
black .
isort .
```

## License

MIT License