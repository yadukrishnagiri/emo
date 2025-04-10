import ffmpeg
import os
import requests
import time
import json
import cv2
import numpy as np
import mediapipe as mp
from datetime import datetime
import google.generativeai as genai
import tkinter as tk
from tkinter import filedialog
from chroma_cache import SpeechAnalysisCache
from ai_report_generator import AIReportGenerator

# Replace with your AssemblyAI API key
API_KEY = "3af788588a404358aa3edf58900d1fcc"  # Get from https://www.assemblyai.com/

# Initialize cache
speech_cache = SpeechAnalysisCache()

def analyze_audio(audio_path):
    """Analyze audio using AssemblyAI with ChromaDB caching"""
    try:
        print("Checking cache for audio analysis...")
        # Try to get analysis from cache first
        cached_analysis = speech_cache.get_cached_analysis(audio_path=audio_path)
        if cached_analysis:
            print("Using cached analysis results")
            return cached_analysis
            
        print("No cached analysis found, processing audio...")
        headers = {
            "authorization": API_KEY,
            "content-type": "application/json"
        }
        
        # Upload the audio file
        print("Uploading audio file...")
        with open(audio_path, "rb") as f:
            upload_response = requests.post(
                "https://api.assemblyai.com/v2/upload",
                headers={"authorization": API_KEY},
                data=f
            )
        
        if upload_response.status_code == 200:
            upload_url = upload_response.json()["upload_url"]
            print("Audio file uploaded successfully")
        else:
            print(f"Upload failed: {upload_response.text}")
            raise Exception("Audio upload failed")

        # Create transcription request
        transcript_response = requests.post(
            "https://api.assemblyai.com/v2/transcript",
            json={
                "audio_url": upload_url,
                "auto_chapters": True,
                "sentiment_analysis": True,
                "entity_detection": True,
                "auto_highlights": True
            },
            headers=headers
        )
        
        if transcript_response.status_code == 200:
            transcript_id = transcript_response.json()['id']
            print(f"Transcription started with ID: {transcript_id}")
        else:
            print(f"Transcription request failed: {transcript_response.text}")
            raise Exception("Transcription request failed")

        # Poll for completion
        while True:
            polling_response = requests.get(
                f"https://api.assemblyai.com/v2/transcript/{transcript_id}",
                headers=headers
            )
            polling_result = polling_response.json()

            if polling_response.status_code == 200:
                status = polling_result['status']
                if status == 'completed':
                    print("Analysis completed successfully!")
                    
                    # Extract metrics
                    words = polling_result.get('words', [])
                    duration = polling_result.get('audio_duration', 0)
                    
                    if words and duration > 0:
                        # Calculate clarity score
                        word_confidences = [word.get('confidence', 0) for word in words]
                        avg_confidence = sum(word_confidences) / len(word_confidences)
                        clarity_score = round(avg_confidence * 100, 2)
                        
                        # Calculate pace
                        words_per_minute = (len(words) / (duration / 60))
                        pace_score = round(min(100, max(0, (words_per_minute / 150) * 100)), 2)
                        
                        # Calculate engagement
                        sentiment_results = polling_result.get('sentiment_analysis_results', [])
                        positive_segments = sum(1 for seg in sentiment_results if seg.get('sentiment') == 'POSITIVE')
                        engagement_score = round((positive_segments / len(sentiment_results) * 100) if sentiment_results else 50, 2)
                        
                        # Create analysis result
                        analysis_result = {
                            "duration_seconds": duration,
                            "overall_sentiment": polling_result.get('sentiment', 'NEUTRAL'),
                            "speech_analysis": {
                                "clarity_score": clarity_score,
                                "pace_score": pace_score,
                                "confidence_score": clarity_score,
                                "engagement_score": engagement_score
                            },
                            "summary": {
                                "total_duration": f"{round(duration, 2)} seconds",
                                "total_words": len(words),
                                "words_per_minute": round(words_per_minute, 2)
                            },
                            "text": polling_result.get('text', ''),
                            "recommendations": []
                        }
                        
                        # Cache the analysis results
                        speech_cache.cache_analysis(analysis_result, audio_path=audio_path)
                        
                        return analysis_result
                    else:
                        print("Warning: No words detected in the audio")
                        raise Exception("No speech detected")
                        
                elif status == 'error':
                    print(f"Analysis failed: {polling_result.get('error')}")
                    raise Exception(f"Analysis failed: {polling_result.get('error')}")
                    
                print(f"Status: {status}... waiting")
                time.sleep(3)
            else:
                print(f"Polling failed: {polling_response.text}")
                raise Exception("Polling failed")

    except Exception as e:
        print(f"Audio analysis error: {str(e)}")
        print("Returning default values")
        return {
            "duration_seconds": 0,
            "overall_sentiment": "NEUTRAL",
            "speech_analysis": {
                "clarity_score": 0,
                "pace_score": 0,
                "confidence_score": 0,
                "engagement_score": 0
            },
            "summary": {
                "total_duration": "0 seconds",
                "total_words": 0,
                "words_per_minute": 0
            },
            "text": "",
            "recommendations": []
        }

def calculate_overall_sentiment(sentiment_results):
    sentiment_counts = {"POSITIVE": 0, "NEUTRAL": 0, "NEGATIVE": 0}
    for result in sentiment_results:
        sentiment_counts[result["sentiment"]] += 1
    
    # Return the dominant sentiment
    return max(sentiment_counts.items(), key=lambda x: x[1])[0]

def calculate_clarity_score(result):
    # Calculate clarity based on confidence scores
    avg_confidence = sum(word["confidence"] for word in result["words"]) / len(result["words"])
    return round(avg_confidence * 100, 2)

def calculate_pace_score(result):
    # Calculate words per minute
    duration_minutes = result["audio_duration"] / 60
    words_count = len(result["words"])
    wpm = words_count / duration_minutes
    
    # Ideal range is 120-160 WPM
    if 120 <= wpm <= 160:
        return 100
    elif wpm < 120:
        return round(100 - ((120 - wpm) / 1.2), 2)
    else:
        return round(100 - ((wpm - 160) / 1.6), 2)

def calculate_confidence_score(sentiment_results):
    """Calculate confidence score from sentiment analysis"""
    if not sentiment_results:
        return None  # Return None if no data
    
    positive_segments = sum(1 for segment in sentiment_results if segment["sentiment"] == "POSITIVE")
    score = (positive_segments / len(sentiment_results)) * 100
    return 0.0 if score == 0 else score

def calculate_engagement_score(result):
    """Calculate engagement score"""
    if not result or "words" not in result:
        return None  # Return None if no data
    
    # Based on variety in tone and pauses
    pauses = sum(1 for word in result["words"] if float(word["end"]) - float(word["start"]) > 0.5)
    pause_ratio = pauses / len(result["words"])
    score = (1 - abs(0.1 - pause_ratio)) * 100  # 10% pauses is ideal
    return 0.0 if score == 0 else score

def generate_summary(result):
    return {
        "total_duration": f"{result['audio_duration']} seconds",
        "total_words": len(result["words"]),
        "words_per_minute": round(len(result["words"]) / (result["audio_duration"] / 60), 2)
    }

def generate_recommendations(result):
    recommendations = []
    
    # Add recommendations based on analysis
    clarity_score = calculate_clarity_score(result)
    pace_score = calculate_pace_score(result)
    
    if clarity_score < 80:
        recommendations.append("Work on speech clarity and pronunciation")
    if pace_score < 70:
        recommendations.append("Adjust speaking pace - aim for 120-160 words per minute")
    
    return recommendations

def get_next_candidate_number(base_path):
    """Get the next available candidate number by checking existing files"""
    existing_files = []
    # Check all relevant directories
    dirs_to_check = ['video', 'audio', 'report']
    
    for dir_name in dirs_to_check:
        dir_path = os.path.join(os.path.dirname(base_path), dir_name)
        if os.path.exists(dir_path):
            files = [f for f in os.listdir(dir_path) if 'candidate_' in f]
            existing_files.extend(files)
    
    if not existing_files:
        return 1
        
    # Extract numbers from existing files
    numbers = []
    for file in existing_files:
        try:
            num = int(file.split('candidate_')[1].split('.')[0])
            numbers.append(num)
        except:
            continue
    
    return max(numbers) + 1 if numbers else 1

def get_candidate_info():
    """Get candidate information from user"""
    print("\n=== Candidate Information ===")
    name = input("Enter candidate name: ")
    id_number = input("Enter candidate ID number: ")
    return name, id_number

def get_candidate_paths(base_path, name, id_number):
    """Generate paths for all files with candidate name and ID"""
    # Create folder name using name and ID
    folder_name = f"{name}_{id_number}"
    
    directories = {
        'video': os.path.join(base_path, 'video'),
        'audio': os.path.join(base_path, 'audio'),
        'report': os.path.join(base_path, 'report')
    }
    
    # Create directories if they don't exist
    for dir_path in directories.values():
        os.makedirs(dir_path, exist_ok=True)
    
    return {
        'video': os.path.join(directories['video'], f'{folder_name}.mp4'),
        'audio': os.path.join(directories['audio'], f'{folder_name}.mp3'),
        'report': os.path.join(directories['report'], f'{folder_name}.json'),
        'evaluation': os.path.join(directories['report'], f'{folder_name}_evaluation.txt'),
        'score': os.path.join(directories['report'], f'{folder_name}_score.txt')
    }

def analyze_video(video_path):
    """Analyze video using OpenCV and basic face detection"""
    try:
        cap = cv2.VideoCapture(video_path)
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        
        metrics = {
            "facial_expressions": {
                "smile_warmth": 0,
                "eye_contact": 0,
                "genuineness": 0
            },
            "posture": {
                "upright_confident": 0,
                "balance": 0
            },
            "overall_energy": {
                "engagement": 0
            }
        }
        
        frames_processed = 0
        face_detected = 0
        face_sizes = []
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
                
            frames_processed += 1
            if frames_processed % 5 != 0:  # Process every 5th frame
                continue
            
            # Convert to grayscale for face detection
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, 1.1, 4)
            
            if len(faces) > 0:
                face_detected += 1
                x, y, w, h = faces[0]  # Get the first face
                face_sizes.append(w * h)
                
                # Calculate metrics based on face position and size
                frame_height, frame_width = frame.shape[:2]
                center_x = x + w/2
                center_y = y + h/2
                
                # Eye contact based on face position
                if 0.3 < center_x/frame_width < 0.7 and 0.3 < center_y/frame_height < 0.7:
                    metrics["facial_expressions"]["eye_contact"] += 1
                
                # Posture based on face size consistency
                if len(face_sizes) > 1 and abs(face_sizes[-1] - face_sizes[-2]) < 1000:
                    metrics["posture"]["upright_confident"] += 1
                
                # Engagement based on face presence and position
                metrics["overall_energy"]["engagement"] += 1
                metrics["facial_expressions"]["genuineness"] += 1
        
        # Normalize metrics
        if face_detected > 0:
            for category in metrics:
                for metric in metrics[category]:
                    metrics[category][metric] = round((metrics[category][metric] / face_detected) * 100, 2)
        
        cap.release()
        
        return {
            "metrics": metrics,
            "frames_analyzed": frames_processed,
            "face_detection_rate": round((face_detected / frames_processed) * 100, 2)
        }
        
    except Exception as e:
        print(f"Video analysis error: {str(e)}")
        return {
            "metrics": metrics,
            "error": f"Analysis completed with reduced accuracy: {str(e)}"
        }

def format_metric_value(value):
    """Format metric values for the report"""
    if value is None:
        return "N/A"
    elif value == 0:
        return 0.0
    return float(value)

def generate_report(audio_analysis, video_analysis):
    """Generate final report with proper value formatting"""
    report = {
        "audio_analysis": {
            "duration_seconds": audio_analysis.get("duration_seconds", None),
            "overall_sentiment": audio_analysis.get("overall_sentiment", "N/A"),
            "speech_analysis": {
                "clarity_score": format_metric_value(audio_analysis.get("clarity_score")),
                "pace_score": format_metric_value(audio_analysis.get("pace_score")),
                "confidence_score": format_metric_value(audio_analysis.get("confidence_score")),
                "engagement_score": format_metric_value(audio_analysis.get("engagement_score"))
            }
        },
        "video_analysis": {
            "metrics": {
                category: {
                    metric: format_metric_value(value)
                    for metric, value in metrics.items()
                }
                for category, metrics in video_analysis["metrics"].items()
            }
        }
    }
    return report

def extract_content(video_path, paths, candidate_name, candidate_id):
    try:
        print("\n=== Starting Extraction Process ===")
        print("This may take a few minutes...")
        
        # Process files
        print("\n1. Processing Audio...")
        stream = ffmpeg.input(video_path)
        stream = ffmpeg.output(stream, paths['audio'], acodec='libmp3lame', ac=1, ar='16k')
        ffmpeg.run(stream, overwrite_output=True, quiet=True)  # Added quiet=True
        print("✓ Audio extracted successfully")
        
        print("\n2. Processing Video...")
        stream = ffmpeg.input(video_path)
        stream = ffmpeg.output(stream, paths['video'], an=None)
        ffmpeg.run(stream, overwrite_output=True, quiet=True)  # Added quiet=True
        print("✓ Video processed successfully")
        
        print("\n3. Analyzing Audio (this may take a minute)...")
        analysis = analyze_audio(paths['audio'])
        print("✓ Audio analysis complete")
        
        print("\n4. Analyzing Video...")
        video_analysis = analyze_video(video_path)
        print("✓ Video analysis complete")
        
        full_analysis = {
            "audio_analysis": analysis,
            "video_analysis": video_analysis,
            "transcript": analysis.get('text', '')
        }
        
        print("\n5. Generating Reports...")
        # Save JSON report
        with open(paths['report'], 'w', encoding='utf-8') as f:
            json.dump(full_analysis, f, indent=4)
        print("✓ JSON report saved")
        
        # Generate AI evaluation using the cached generator
        api_key = "AIzaSyB5tQYKNZM8TMkvTmnfwnRK7p0nwWDA0Yo"
        print("\n6. Generating AI Evaluation...")
        
        # Initialize the AI report generator with caching
        report_generator = AIReportGenerator(api_key)
        evaluation_text, score = report_generator.generate_report(full_analysis)
        
        print("✓ AI evaluation complete")
        
        try:
            print("\n7. Saving Files Locally...")
            # Save local files
            with open(paths['evaluation'], 'w', encoding='utf-8') as f:
                f.write(evaluation_text)
            with open(paths['score'], 'w') as f:
                f.write(f"Final Score: {score}/100")
            print("✓ Local files saved")
            
            print("\n=== Process Complete ===")
            print(f"Candidate: {candidate_name} (ID: {candidate_id})")
            print(f"Final Score: {score}/100")
            print("\nFiles created:")
            print(f"✓ Video: {paths['video']}")
            print(f"✓ Audio: {paths['audio']}")
            print(f"✓ JSON Report: {paths['report']}")
            print(f"✓ Evaluation: {paths['evaluation']}")
            print(f"✓ Score: {paths['score']}")
            
        except Exception as e:
            print(f"\n❌ Error saving files: {str(e)}")
            raise
            
    except Exception as e:
        print(f"\n❌ Error during processing: {str(e)}")
        raise

# Add these helper functions
def detect_blink(landmarks):
    """Detect eye blink from landmarks"""
    left_eye = landmarks.landmark[159]  # Left eye point
    right_eye = landmarks.landmark[386]  # Right eye point
    return abs(left_eye.y - right_eye.y) < 0.01

def calculate_balance(pose_landmarks):
    """Calculate body balance from pose"""
    hip_left = pose_landmarks.landmark[23]
    hip_right = pose_landmarks.landmark[24]
    return 1.0 if abs(hip_left.y - hip_right.y) < 0.1 else 0.5

def calculate_speech_alignment(pose_landmarks):
    """Calculate alignment between speech and body movement"""
    # Simplified version using shoulder movement
    return 1.0

def generate_text_report(analysis, paths):
    """Generate a human-readable text report"""
    try:
        text_report = f"""Interview Analysis Report
=========================
Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Audio Analysis
-------------
Duration: {analysis['audio_analysis']['duration_seconds']} seconds
Overall Sentiment: {analysis['audio_analysis']['overall_sentiment']}

Speech Analysis:
- Clarity Score: {analysis['audio_analysis']['speech_analysis']['clarity_score']}%
- Pace Score: {analysis['audio_analysis']['speech_analysis']['pace_score']}%
- Confidence Score: {analysis['audio_analysis']['speech_analysis']['confidence_score']}%
- Engagement Score: {analysis['audio_analysis']['speech_analysis']['engagement_score']}%

Video Analysis
-------------
Facial Expressions:
- Genuineness: {analysis['video_analysis']['metrics']['facial_expressions']['genuineness']}%
- Smile Warmth: {analysis['video_analysis']['metrics']['facial_expressions']['smile_warmth']}%
- Eye Contact: {analysis['video_analysis']['metrics']['facial_expressions']['eye_contact']}%
- Emotional Consistency: {analysis['video_analysis']['metrics']['facial_expressions']['emotional_consistency']}%
- Microexpressions: {analysis['video_analysis']['metrics']['facial_expressions']['microexpressions']}%

Eye Movement:
- Direct Engagement: {analysis['video_analysis']['metrics']['eye_movement']['direct_engagement']}%
- Confidence: {analysis['video_analysis']['metrics']['eye_movement']['confidence']}%
- Natural Blinking: {analysis['video_analysis']['metrics']['eye_movement']['natural_blinking']}%

Posture:
- Upright Confidence: {analysis['video_analysis']['metrics']['posture']['upright_confident']}%
- Openness: {analysis['video_analysis']['metrics']['posture']['openness']}%
- Balance: {analysis['video_analysis']['metrics']['posture']['balance']}%

Overall Energy:
- Speech Alignment: {analysis['video_analysis']['metrics']['overall_energy']['speech_alignment']}%
- Engagement: {analysis['video_analysis']['metrics']['overall_energy']['engagement']}%

Recommendations
--------------"""

        # Add audio recommendations
        if 'recommendations' in analysis['audio_analysis']:
            text_report += "\nAudio Recommendations:"
            for rec in analysis['audio_analysis']['recommendations']:
                text_report += f"\n- {rec}"

        # Add video recommendations
        if 'recommendations' in analysis['video_analysis']:
            text_report += "\n\nVideo Recommendations:"
            for rec in analysis['video_analysis']['recommendations']:
                text_report += f"\n- {rec}"

        # Create text report path
        text_report_path = paths['report'].replace('.json', '.txt')
        
        # Save text report
        with open(text_report_path, 'w', encoding='utf-8') as f:
            f.write(text_report)
            
        print(f"Text report saved: {os.path.exists(text_report_path)}")
        
    except Exception as e:
        print(f"Error generating text report: {str(e)}")

def generate_ai_report(analysis_data, paths, api_key):
    """
    Legacy function, maintained for backward compatibility.
    Now uses the AIReportGenerator class for report generation with caching.
    """
    report_generator = AIReportGenerator(api_key)
    return report_generator.generate_report(analysis_data)

def detect_microexpression(landmarks):
    """Detect subtle facial movements"""
    try:
        # Use eye and mouth points for expression detection
        left_eye = landmarks.landmark[159]  # Left eye point
        right_eye = landmarks.landmark[386]  # Right eye point
        mouth_top = landmarks.landmark[13]   # Upper lip
        mouth_bottom = landmarks.landmark[14] # Lower lip
        
        # Calculate mouth movement
        mouth_height = abs(mouth_top.y - mouth_bottom.y)
        # Calculate eye movement
        eye_diff = abs(left_eye.y - right_eye.y)
        
        # Return true if either mouth or eyes show movement
        return mouth_height > 0.01 or eye_diff < 0.01
    except:
        return False

def get_candidate_evaluation(candidate_id):
    """Get candidate evaluation from database"""
    try:
        # Return None to indicate no database functionality
        return None
    except Exception as e:
        print(f"Error getting candidate evaluation: {str(e)}")
        return None

if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    
    # Get candidate information first
    candidate_name, candidate_id = get_candidate_info()
    
    video_file = filedialog.askopenfilename(
        title="Select Video File",
        filetypes=[("Video files", "*.mp4 *.avi *.mkv *.mov")]
    )
    
    if video_file:
        base_path = r"C:\Users\yaduk\OneDrive\Desktop\Projects\major\emo"
        
        # Generate paths with candidate info
        paths = get_candidate_paths(base_path, candidate_name, candidate_id)
        
        # Extract content with candidate info
        extract_content(video_file, paths, candidate_name, candidate_id)
    else:
        print("No file selected") 