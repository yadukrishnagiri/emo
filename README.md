# Emotion Analysis and Candidate Evaluation System

This project is an AI-powered system that analyzes candidate interview videos to provide comprehensive evaluations based on audio and video analysis.

## Features

- **Audio Analysis**: Extracts speech clarity, pace, confidence, and sentiment using AssemblyAI
- **Video Analysis**: Evaluates eye contact, facial expressions, posture, and engagement
- **AI-Generated Reports**: Creates detailed evaluation reports with scores and recommendations
- **Local Storage**: Saves all analysis files locally
- **ChromaDB Caching**: Reduces API token usage by caching analysis results

## Components

- `extract_audio.py`: Main module for video processing and analysis
- `candidate_evaluator.py`: Alternative UI-based evaluation tool
- `chroma_cache.py`: Implements ChromaDB caching for speech analysis
- `ai_report_generator.py`: Provides AI report generation with caching
- `test.py`: Testing script for report generation

## ChromaDB Implementation

The system uses ChromaDB for efficient caching of:

1. **Speech Analysis Results**: Caches results from AssemblyAI API calls to avoid reprocessing the same audio files
2. **AI-Generated Reports**: Stores previously generated Gemini AI reports to reduce token usage

### How Caching Works

- Audio files and transcripts are hashed to create unique IDs
- Analysis results are stored in ChromaDB collections
- Before making API calls, the system checks for cached results
- If cached results exist, they're used instead of making new API calls
- This significantly reduces API token usage and speeds up processing

## Usage

1. Activate the virtual environment:
   ```
   .\venv\Scripts\activate
   ```

2. Run the main extraction tool:
   ```
   python extract_audio.py
   ```

3. Follow the prompts to:
   - Enter candidate name and ID
   - Select a video file for analysis
   
4. Analysis files will be saved in the corresponding directories:
   - `/video/`: Processed video files
   - `/audio/`: Extracted audio files
   - `/report/`: JSON reports, evaluations, and scores

## Requirements

- Python 3.8+
- FFmpeg
- AssemblyAI API key
- Google Gemini API key
- Required Python packages (see requirements.txt)

## API Token Efficiency

The ChromaDB caching system significantly reduces API token usage by:

1. Avoiding duplicate AssemblyAI transcription requests
2. Reusing Gemini AI reports for similar analyses
3. Providing fallback mechanisms when API services are unavailable

This results in faster processing times and lower costs while maintaining accuracy. 