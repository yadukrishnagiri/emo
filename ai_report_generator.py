import os
import json
import hashlib
import google.generativeai as genai
from datetime import datetime
import chromadb
from chromadb.utils import embedding_functions

class AIReportGenerator:
    """
    Generates AI reports for candidate evaluations with ChromaDB caching
    to reduce API token usage.
    """
    def __init__(self, api_key, persist_directory="./chroma_db"):
        """Initialize the AI report generator with ChromaDB caching"""
        # Configure Gemini API
        genai.configure(api_key=api_key)
        
        # Initialize model
        try:
            self.model = genai.GenerativeModel('gemini-2.0-flash')
            print("Gemini AI model initialized successfully")
        except Exception as e:
            print(f"Error initializing Gemini model: {str(e)}")
            self.model = None
        
        # Create ChromaDB directory if it doesn't exist
        os.makedirs(persist_directory, exist_ok=True)
        
        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(path=persist_directory)
        
        # Use the default embedding function
        self.embedding_func = embedding_functions.DefaultEmbeddingFunction()
        
        # Create or get collection for AI reports
        self.collection = self.client.get_or_create_collection(
            name="ai_reports",
            embedding_function=self.embedding_func,
            metadata={"description": "Cache of AI-generated evaluation reports"}
        )
        
        print(f"ChromaDB initialized with collection: ai_reports")
    
    def generate_hash(self, analysis_data):
        """Generate a hash from analysis data for caching"""
        # Convert analysis data to a stable string representation
        analysis_str = json.dumps(analysis_data, sort_keys=True)
        return hashlib.md5(analysis_str.encode('utf-8')).hexdigest()
    
    def get_cached_report(self, analysis_data):
        """Try to retrieve a cached report"""
        try:
            # Generate hash from analysis data
            doc_id = self.generate_hash(analysis_data)
            
            # Query the collection
            results = self.collection.get(
                ids=[doc_id],
                include=["metadatas", "documents"]
            )
            
            # Check if we got results
            if results and results['ids'] and len(results['ids']) > 0:
                # Parse the cached data
                cached_data = json.loads(results['documents'][0])
                print(f"✓ Retrieved cached AI report from ChromaDB (ID: {doc_id[:8]}...)")
                return cached_data.get("evaluation_text"), cached_data.get("score")
            
            print(f"No cached AI report found for ID: {doc_id[:8]}...")
            return None, None
            
        except Exception as e:
            print(f"Error retrieving cached report: {str(e)}")
            return None, None
    
    def cache_report(self, analysis_data, evaluation_text, score):
        """Cache the generated report"""
        try:
            # Generate hash from analysis data
            doc_id = self.generate_hash(analysis_data)
            
            # Convert to string for storage
            cached_data = {
                "evaluation_text": evaluation_text,
                "score": score
            }
            document = json.dumps(cached_data)
            
            # Extract transcript for embedding
            transcript = analysis_data.get("transcript", "")[:1000]
            
            # Store in collection
            self.collection.upsert(
                ids=[doc_id],
                documents=[document],
                metadatas=[{
                    "cached_date": datetime.now().isoformat(),
                    "transcript_length": len(analysis_data.get("transcript", "")),
                    "score": score
                }]
            )
            
            print(f"✓ Cached AI report in ChromaDB (ID: {doc_id[:8]}...)")
            return True
            
        except Exception as e:
            print(f"Error caching report: {str(e)}")
            return False
    
    def generate_report(self, analysis_data):
        """
        Generate an AI evaluation report with caching
        
        Args:
            analysis_data: Dictionary containing audio and video analysis
            
        Returns:
            evaluation_text: The generated report text
            score: The calculated score
        """
        # First check if we have a cached report
        evaluation_text, score = self.get_cached_report(analysis_data)
        if evaluation_text and score:
            return evaluation_text, score
        
        # If not cached, calculate score first
        score = self._calculate_score(analysis_data)
        
        # If model is not available, return basic report
        if not self.model:
            evaluation_text = self._generate_basic_report(analysis_data, score)
            # Cache the report
            self.cache_report(analysis_data, evaluation_text, score)
            return evaluation_text, score
        
        # Generate prompt for Gemini
        prompt = self._create_prompt(analysis_data)
        
        try:
            # Generate the report using Gemini
            response = self.model.generate_content(prompt)
            evaluation_text = response.text
            
            # Cache the report
            self.cache_report(analysis_data, evaluation_text, score)
            
            return evaluation_text, score
            
        except Exception as e:
            print(f"Error generating AI report: {str(e)}")
            # Fall back to basic report
            evaluation_text = self._generate_basic_report(analysis_data, score)
            return evaluation_text, score
    
    def _calculate_score(self, analysis_data):
        """Calculate an overall score from the metrics"""
        try:
            score = int((
                analysis_data['audio_analysis']['speech_analysis']['clarity_score'] +
                analysis_data['audio_analysis']['speech_analysis']['pace_score'] +
                analysis_data['video_analysis']['metrics']['facial_expressions']['eye_contact'] +
                analysis_data['video_analysis']['metrics']['facial_expressions']['genuineness'] +
                analysis_data['video_analysis']['metrics']['posture']['upright_confident'] +
                analysis_data['video_analysis']['metrics']['overall_energy']['engagement']
            ) / 6)
            
            return score
        except KeyError as e:
            print(f"Error calculating score (missing key: {str(e)}), using default")
            return 70  # Default score
    
    def _create_prompt(self, analysis_data):
        """Create the prompt for Gemini API"""
        prompt = f"""
        Generate a professional candidate evaluation report based on the following analysis:

        Audio Analysis:
        - Duration: {analysis_data['audio_analysis']['duration_seconds']} seconds
        - Sentiment: {analysis_data['audio_analysis']['overall_sentiment']}
        - Clarity Score: {analysis_data['audio_analysis']['speech_analysis']['clarity_score']}%
        - Pace Score: {analysis_data['audio_analysis']['speech_analysis']['pace_score']}%
        - Confidence Score: {analysis_data['audio_analysis']['speech_analysis']['confidence_score']}%
        - Words per Minute: {analysis_data['audio_analysis']['summary']['words_per_minute']}

        Video Analysis:
        - Eye Contact: {analysis_data['video_analysis']['metrics']['facial_expressions']['eye_contact']}%
        - Genuineness: {analysis_data['video_analysis']['metrics']['facial_expressions']['genuineness']}%
        - Posture Confidence: {analysis_data['video_analysis']['metrics']['posture']['upright_confident']}%
        - Engagement: {analysis_data['video_analysis']['metrics']['overall_energy']['engagement']}%

        Transcript:
        {analysis_data['transcript']}

        Please provide:
        1. Executive Summary
        2. Communication Skills Assessment
        3. Body Language Analysis
        4. Technical Knowledge Evaluation
        5. Overall Impression
        6. Recommendations for Improvement
        7. Final Score is {self._calculate_score(analysis_data)}/100
        """
        
        return prompt
    
    def _generate_basic_report(self, analysis_data, score):
        """Generate a basic report if the AI model is not available"""
        recommendations = self._generate_recommendations(analysis_data)
        
        report = f"""## Candidate Evaluation Report

**1. Executive Summary:**
The candidate demonstrated {analysis_data['audio_analysis']['overall_sentiment'].lower()} communication with clarity score of {analysis_data['audio_analysis']['speech_analysis']['clarity_score']}% and engagement level of {analysis_data['video_analysis']['metrics']['overall_energy']['engagement']}%.

**2. Communication Skills Assessment:**
- Clarity Score: {analysis_data['audio_analysis']['speech_analysis']['clarity_score']}%
- Pace Score: {analysis_data['audio_analysis']['speech_analysis']['pace_score']}%
- Words per Minute: {analysis_data['audio_analysis']['summary']['words_per_minute']}
- Overall Sentiment: {analysis_data['audio_analysis']['overall_sentiment']}

**3. Body Language Analysis:**
- Eye Contact: {analysis_data['video_analysis']['metrics']['facial_expressions']['eye_contact']}%
- Genuineness: {analysis_data['video_analysis']['metrics']['facial_expressions']['genuineness']}%
- Posture Confidence: {analysis_data['video_analysis']['metrics']['posture']['upright_confident']}%
- Engagement: {analysis_data['video_analysis']['metrics']['overall_energy']['engagement']}%

**4. Technical Knowledge Evaluation:**
Based on transcript analysis:
{analysis_data.get('transcript', 'No transcript available')}

**5. Overall Impression:**
The candidate shows {analysis_data['video_analysis']['metrics']['facial_expressions']['genuineness']}% genuineness in expressions and {analysis_data['video_analysis']['metrics']['posture']['upright_confident']}% confidence in posture.

**6. Recommendations for Improvement:**
{recommendations}

**7. Final Score:**
{score}/100
"""
        return report
    
    def _generate_recommendations(self, data):
        """Generate specific recommendations based on scores"""
        recommendations = []
        
        if data['audio_analysis']['speech_analysis']['clarity_score'] < 90:
            recommendations.append("- Work on speech clarity and pronunciation")
        if data['audio_analysis']['speech_analysis']['pace_score'] < 90:
            recommendations.append("- Adjust speaking pace to improve delivery")
        if data['video_analysis']['metrics']['facial_expressions']['eye_contact'] < 90:
            recommendations.append("- Maintain more consistent eye contact")
        if data['video_analysis']['metrics']['posture']['upright_confident'] < 90:
            recommendations.append("- Improve posture to project more confidence")
        
        if not recommendations:
            recommendations.append("- Continue maintaining current performance levels")
        
        return "\n".join(recommendations) 