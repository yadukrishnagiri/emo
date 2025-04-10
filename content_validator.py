import cv2
import numpy as np
import os
import mediapipe as mp
import subprocess
import json
import re
import requests

class ContentValidator:
    """
    Validates that a video contains proper candidate interview content
    and not random content like animals, machinery, etc.
    """
    def __init__(self):
        # Initialize face detection
        self.mp_face_detection = mp.solutions.face_detection
        self.mp_face_mesh = mp.solutions.face_mesh
        self.mp_drawing = mp.solutions.drawing_utils
        
        # Keywords that should appear in interview transcripts
        self.interview_keywords = [
            'experience', 'skill', 'education', 'job', 'position', 'work', 
            'project', 'team', 'background', 'responsibility', 'career',
            'qualification', 'challenge', 'goal', 'achievement', 'degree',
            'professional', 'interview', 'thank you', 'resume', 'cv',
            'opportunity', 'position', 'role', 'candidate', 'hire'
        ]
        
        # Keywords that suggest non-interview content
        self.non_interview_keywords = [
            'cat', 'dog', 'pet', 'animal', 'game', 'play', 'movie', 'trailer',
            'funny', 'cooking', 'recipe', 'music', 'song', 'dance', 'travel',
            'vacation', 'machine', 'engine', 'vehicle', 'tutorial', 'gameplay',
            'unboxing', 'review', 'prank', 'magic', 'trick', 'vlog'
        ]
        
    def get_transcript_sample(self, audio_path, api_key):
        """
        Get a transcript sample to validate content
        Uses a smaller segment to minimize API usage
        """
        try:
            # Get first 10 seconds of audio
            temp_sample_path = audio_path.replace('.mp3', '_sample.mp3')
            
            # Use ffmpeg to extract first 10 seconds
            subprocess.run([
                'ffmpeg', '-i', audio_path, 
                '-t', '10', '-c:a', 'copy', 
                temp_sample_path
            ], capture_output=True)
            
            if not os.path.exists(temp_sample_path):
                return None
                
            # Get a transcript sample using AssemblyAI
            headers = {
                "authorization": api_key,
                "content-type": "application/json"
            }
            
            # Upload the audio sample
            with open(temp_sample_path, "rb") as f:
                upload_response = requests.post(
                    "https://api.assemblyai.com/v2/upload",
                    headers={"authorization": api_key},
                    data=f
                )
            
            if upload_response.status_code != 200:
                return None
                
            upload_url = upload_response.json()["upload_url"]
            
            # Create transcription request
            transcript_response = requests.post(
                "https://api.assemblyai.com/v2/transcript",
                json={"audio_url": upload_url},
                headers=headers
            )
            
            if transcript_response.status_code != 200:
                return None
                
            transcript_id = transcript_response.json()['id']
            
            # Poll for completion (with timeout after 5 attempts)
            attempts = 0
            while attempts < 5:
                polling_response = requests.get(
                    f"https://api.assemblyai.com/v2/transcript/{transcript_id}",
                    headers=headers
                )
                
                if polling_response.status_code == 200:
                    status = polling_response.json()['status']
                    if status == 'completed':
                        text = polling_response.json().get('text', '')
                        
                        # Clean up temporary file
                        try:
                            os.remove(temp_sample_path)
                        except:
                            pass
                            
                        return text
                        
                attempts += 1
                import time
                time.sleep(2)
                
            return None
            
        except Exception as e:
            print(f"Error getting transcript sample: {str(e)}")
            return None
            
    def validate_video(self, video_path, audio_path=None, api_key=None):
        """
        Validates if a video is likely to be a candidate interview
        
        Returns:
            dict: Validation results with confidence score and reason
        """
        results = {
            "is_valid": False,
            "confidence": 0,
            "reason": "Unknown",
            "checks": {}
        }
        
        # Check if file exists
        if not os.path.exists(video_path):
            results["reason"] = "Video file does not exist"
            return results
            
        # 1. Check for human face presence
        face_check = self.check_for_human_face(video_path)
        results["checks"]["face_detection"] = face_check
        
        # 2. Check for consistent speaking person
        speaking_check = self.check_for_speaking_person(video_path)
        results["checks"]["speaking_person"] = speaking_check
        
        # 3. Check transcript for interview-related content (if audio_path provided)
        transcript_check = {"passed": False, "score": 0, "details": "No transcript available"}
        if audio_path and api_key and os.path.exists(audio_path):
            transcript_check = self.check_transcript_content(audio_path, api_key)
        results["checks"]["transcript_content"] = transcript_check
        
        # Calculate overall confidence based on all checks
        face_score = face_check.get("score", 0) 
        speaking_score = speaking_check.get("score", 0)
        transcript_score = transcript_check.get("score", 0)
        
        # Weight the scores (face detection is most important)
        # 50% face detection, 30% speaking person, 20% transcript
        weighted_score = (face_score * 0.5) + (speaking_score * 0.3)
        
        if transcript_score > 0:
            weighted_score += (transcript_score * 0.2)
        else:
            # Adjust weights if no transcript check
            weighted_score = (face_score * 0.6) + (speaking_score * 0.4)
        
        results["confidence"] = round(weighted_score, 2)
        
        # Determine if valid based on confidence threshold
        if results["confidence"] >= 70:
            results["is_valid"] = True
            results["reason"] = "Passed validation checks with sufficient confidence"
        else:
            results["is_valid"] = False
            
            # Determine the specific reason for failure
            if face_score < 40:
                results["reason"] = "Insufficient face detection"
            elif speaking_score < 40:
                results["reason"] = "No consistent speaking person detected"
            elif transcript_score < 30 and transcript_check.get("details"):
                results["reason"] = f"Non-interview content detected: {transcript_check.get('details')}"
            else:
                results["reason"] = "Multiple validation checks failed"
        
        return results
    
    def check_for_human_face(self, video_path):
        """
        Check if the video contains a consistent human face
        """
        result = {
            "passed": False,
            "score": 0,
            "details": "No faces detected"
        }
        
        try:
            cap = cv2.VideoCapture(video_path)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            duration = total_frames / fps if fps > 0 else 0
            
            if total_frames <= 0 or duration <= 1:
                result["details"] = "Video too short or invalid"
                return result
                
            # Sample frames every 2 seconds
            sample_interval = int(fps * 2) if fps > 0 else 30
            sample_interval = max(1, sample_interval)  # Ensure at least 1
            
            face_frames = 0
            frames_sampled = 0
            face_sizes = []
            face_positions = []
            
            with self.mp_face_detection.FaceDetection(
                model_selection=1, min_detection_confidence=0.5
            ) as face_detection:
                frame_idx = 0
                
                while cap.isOpened() and frames_sampled < 15:  # Limit to 15 samples
                    ret, frame = cap.read()
                    if not ret:
                        break
                        
                    if frame_idx % sample_interval == 0:
                        frames_sampled += 1
                        
                        # Convert to RGB for MediaPipe
                        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        results = face_detection.process(rgb_frame)
                        
                        if results.detections:
                            face_frames += 1
                            
                            # Get primary face bounding box
                            detection = results.detections[0]
                            bbox = detection.location_data.relative_bounding_box
                            h, w, _ = frame.shape
                            
                            # Store face size (area)
                            face_area = (bbox.width * w) * (bbox.height * h)
                            face_sizes.append(face_area)
                            
                            # Store face position (center)
                            x_center = bbox.xmin + (bbox.width / 2)
                            y_center = bbox.ymin + (bbox.height / 2)
                            face_positions.append((x_center, y_center))
                    
                    frame_idx += 1
                    
                cap.release()
                
                if frames_sampled == 0:
                    return result
                
                # Calculate face detection rate
                face_detection_rate = (face_frames / frames_sampled) * 100
                
                # Check for consistent face size (no extreme variations)
                face_size_consistency = 100
                if len(face_sizes) > 1:
                    mean_size = sum(face_sizes) / len(face_sizes)
                    if mean_size > 0:
                        variations = [abs(s - mean_size) / mean_size for s in face_sizes]
                        face_size_consistency = 100 - (sum(variations) / len(variations) * 100)
                        face_size_consistency = max(0, min(100, face_size_consistency))
                
                # Check for consistent face position (not jumping around)
                position_consistency = 100
                if len(face_positions) > 1:
                    mean_x = sum(p[0] for p in face_positions) / len(face_positions)
                    mean_y = sum(p[1] for p in face_positions) / len(face_positions)
                    
                    variations = [
                        ((p[0] - mean_x) ** 2 + (p[1] - mean_y) ** 2) ** 0.5
                        for p in face_positions
                    ]
                    
                    position_consistency = 100 - (sum(variations) / len(variations) * 100)
                    position_consistency = max(0, min(100, position_consistency))
                
                # Calculate overall score
                overall_score = (
                    face_detection_rate * 0.7 +
                    face_size_consistency * 0.15 +
                    position_consistency * 0.15
                )
                
                result["score"] = round(overall_score, 2)
                result["passed"] = overall_score >= 70
                
                if face_frames == 0:
                    result["details"] = "No faces detected"
                elif face_detection_rate < 50:
                    result["details"] = "Inconsistent face detection"
                elif face_size_consistency < 50:
                    result["details"] = "Highly variable face size (possible multiple subjects)"
                elif position_consistency < 50:
                    result["details"] = "Erratic face movement (unstable video)"
                else:
                    result["details"] = f"Face detected in {face_detection_rate:.1f}% of frames"
                
                return result
                
        except Exception as e:
            result["details"] = f"Error during face detection: {str(e)}"
            return result
            
    def check_for_speaking_person(self, video_path):
        """
        Check if the video shows a person speaking consistently
        """
        result = {
            "passed": False,
            "score": 0,
            "details": "Unable to detect speaking person"
        }
        
        try:
            cap = cv2.VideoCapture(video_path)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            
            if total_frames <= 0:
                result["details"] = "Invalid video file"
                return result
                
            # Sample frames every 1 second
            sample_interval = int(fps) if fps > 0 else 30
            sample_interval = max(1, sample_interval)
            
            mouth_motion_frames = 0
            frames_sampled = 0
            
            with self.mp_face_mesh.FaceMesh(
                max_num_faces=1,
                refine_landmarks=True,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5
            ) as face_mesh:
                frame_idx = 0
                last_mouth_height = None
                mouth_height_changes = []
                
                while cap.isOpened() and frames_sampled < 15:  # Limit to 15 samples
                    ret, frame = cap.read()
                    if not ret:
                        break
                        
                    if frame_idx % sample_interval == 0:
                        frames_sampled += 1
                        
                        # Convert to RGB for MediaPipe
                        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        results = face_mesh.process(rgb_frame)
                        
                        if results.multi_face_landmarks:
                            landmarks = results.multi_face_landmarks[0]
                            
                            # Get mouth landmarks
                            upper_lip = landmarks.landmark[13]  # Upper lip center
                            lower_lip = landmarks.landmark[14]  # Lower lip center
                            
                            # Calculate mouth opening height
                            mouth_height = abs(upper_lip.y - lower_lip.y)
                            
                            # Check for mouth movement
                            if last_mouth_height is not None:
                                height_change = abs(mouth_height - last_mouth_height)
                                mouth_height_changes.append(height_change)
                                
                                # Significant mouth movement detected
                                if height_change > 0.01:
                                    mouth_motion_frames += 1
                            
                            last_mouth_height = mouth_height
                    
                    frame_idx += 1
                    
                cap.release()
                
                if frames_sampled <= 1:  # Need at least 2 samples to detect motion
                    return result
                
                # Calculate speaking detection rate
                speaking_frames = max(0, frames_sampled - 1)  # First frame can't detect change
                speaking_rate = (mouth_motion_frames / speaking_frames) * 100 if speaking_frames > 0 else 0
                
                # Calculate mouth movement consistency
                movement_consistency = 0
                if mouth_height_changes:
                    # Calculate variance in mouth movements
                    mean_change = sum(mouth_height_changes) / len(mouth_height_changes)
                    if mean_change > 0:
                        variance = sum((c - mean_change) ** 2 for c in mouth_height_changes) / len(mouth_height_changes)
                        normalized_variance = min(1.0, variance / (mean_change ** 2))
                        movement_consistency = 100 * (1 - normalized_variance)
                
                # Calculate overall score
                overall_score = speaking_rate * 0.8 + movement_consistency * 0.2
                
                result["score"] = round(overall_score, 2)
                result["passed"] = overall_score >= 60
                
                if mouth_motion_frames == 0:
                    result["details"] = "No mouth movement detected"
                elif speaking_rate < 30:
                    result["details"] = "Limited speaking detected"
                else:
                    result["details"] = f"Speaking detected in {speaking_rate:.1f}% of samples"
                
                return result
                
        except Exception as e:
            result["details"] = f"Error during speaking detection: {str(e)}"
            return result
    
    def check_transcript_content(self, audio_path, api_key):
        """
        Check transcript content for interview-related keywords
        """
        result = {
            "passed": False,
            "score": 0,
            "details": "No transcript available"
        }
        
        try:
            # Get a sample transcript
            transcript = self.get_transcript_sample(audio_path, api_key)
            
            if not transcript or len(transcript) < 10:
                return result
                
            # Convert to lowercase for matching
            transcript_lower = transcript.lower()
            
            # Count interview keywords
            interview_keyword_count = sum(
                1 for keyword in self.interview_keywords 
                if keyword.lower() in transcript_lower
            )
            
            # Count non-interview keywords
            non_interview_keyword_count = sum(
                1 for keyword in self.non_interview_keywords 
                if keyword.lower() in transcript_lower
            )
            
            # Check for common interview phrases
            has_introduction = bool(re.search(r'(my name is|i am|i\'m)\s+\w+', transcript_lower))
            has_background = bool(re.search(r'(experience|background|education|degree|graduated)', transcript_lower))
            has_skills = bool(re.search(r'(skill|ability|proficient|expert|knowledge)', transcript_lower))
            
            # Calculate a weighted interview relevance score
            relevance_score = 0
            
            # Base score from keyword matches
            if interview_keyword_count > 0:
                relevance_score += min(60, interview_keyword_count * 10)
                
            # Penalty for non-interview keywords
            if non_interview_keyword_count > 0:
                relevance_score -= min(relevance_score, non_interview_keyword_count * 15)
                
            # Bonus for interview structural elements
            if has_introduction:
                relevance_score += 15
            if has_background:
                relevance_score += 15
            if has_skills:
                relevance_score += 10
                
            # Cap score at 100
            relevance_score = max(0, min(100, relevance_score))
            
            result["score"] = round(relevance_score, 2)
            result["passed"] = relevance_score >= 50
            
            if non_interview_keyword_count > interview_keyword_count:
                result["details"] = f"Detected {non_interview_keyword_count} non-interview keywords"
            elif interview_keyword_count == 0:
                result["details"] = "No interview-related keywords detected"
            else:
                result["details"] = f"Detected {interview_keyword_count} interview-related keywords"
                
            # Include part of transcript for debugging
            transcript_preview = transcript[:100] + "..." if len(transcript) > 100 else transcript
            result["transcript_preview"] = transcript_preview
            
            return result
            
        except Exception as e:
            result["details"] = f"Error analyzing transcript: {str(e)}"
            return result 