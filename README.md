# AI Multi-Agent Course Summarizer

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-00a393.svg)
![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-FF4B4B.svg)
![LangChain](https://img.shields.io/badge/LangChain-Integration-green.svg)


An advanced, asynchronous AI pipeline that automatically extracts, transcribes, and synthesizes lengthy educational videos and texts into comprehensive study materials using a **Multi-Agent LLM Architecture**.

## Key Features

* **Multi-Agent Orchestration:** Utilizes 5 specialized AI agents (Planner, Summarizer, Quiz Generator, Glossary Extractor, and Reviewer) to autonomously generate structured course data.
* **Hybrid Video Ingestion:** Seamlessly processes YouTube videos via direct closed-caption extraction or fallback audio downloads (`yt-dlp`) transcribed via **OpenAI Whisper**.
* **Zero-Cost Scalability:** Intelligently bypasses free-tier API rate limits ("Burst" Concurrency & TPM limits) via custom **Sequential Queueing** and an **Exponential Backoff** retry loop.
* **LLM Load Balancing:** Dynamically routes traffic across 3 distinct high-capacity models via OpenRouter (`nemotron-120b`, `gemma-31b`, `gpt-oss-20b`) for maximum efficiency.
* **Persistent Caching:** Integrates Redis SHA256 hashing to cache generated course materials, reducing redundant processing time.

## Tech Stack

* **Frontend:** Streamlit
* **Backend:** FastAPI, Python `asyncio`
* **AI & NLP:** LangChain, OpenRouter API (Llama 3, Gemma, Nemotron)
* **Audio Processing:** OpenAI Whisper, `yt-dlp`, FFmpeg
* **Caching:** Redis

## Quick Start

### 1. Prerequisites
* Python 3.10+
* [FFmpeg](https://ffmpeg.org/download.html) installed and added to your system PATH (required for Whisper audio processing).

### 2. Installation
Clone the repository and install the dependencies:
```bash
git clone https://github.com/yourusername/course-summarizer.git
cd course-summarizer
python -m venv venv
source venv/bin/activate  # On Windows: .\venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Environment Variables
Create a `.env` file in the root directory and add your API keys:
```env
OPENROUTER_KEY=your_openrouter_api_key
REDIS_URL=your_redis_connection_url
```

### 4. Running the Application
You need to run both the FastAPI backend and the Streamlit frontend.

**Start the Backend:**
```bash
uvicorn main:app --reload
```

**Start the Frontend:** (In a new terminal)
```bash
streamlit run frontend.py
```

##  How It Works
1. **Input:** The user provides a YouTube URL or raw text.
2. **Extraction:** The backend attempts to fetch YouTube API captions. If unavailable, it downloads the audio via `yt-dlp` and transcribes it locally using Whisper.
3. **Planning:** The `Planner Agent` analyzes the transcript and structures a learning path.
4. **Processing:** The `Summarizer`, `Quiz`, and `Glossary` agents execute sequentially (preventing API burst limits) to generate specialized content.
5. **Review:** The `Reviewer Agent` validates the final output.
6. **Delivery:** The Streamlit UI polls the backend via an async progress tracker and renders the final interactive study guide.

---
*Built to demonstrate robust handling of LLM rate limits and multi-agent asynchronous orchestration.*
