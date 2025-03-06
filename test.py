import json
import google.generativeai as genai

def generate_report_with_gemini(json_file, output_file, api_key):
    try:
        # Configure Gemini
        genai.configure(api_key=api_key)
        
        # Use gemini-2.0-flash model
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        # Read JSON file
        with open(json_file, 'r') as file:
            data = json.load(file)
        
        # Create prompt text
        prompt_text = f"""
        Generate a professional candidate evaluation report based on the following analysis:

        Audio Analysis:
        - Duration: {data['audio_analysis']['duration_seconds']} seconds
        - Sentiment: {data['audio_analysis']['overall_sentiment']}
        - Clarity Score: {data['audio_analysis']['speech_analysis']['clarity_score']}%
        - Pace Score: {data['audio_analysis']['speech_analysis']['pace_score']}%
        - Confidence Score: {data['audio_analysis']['speech_analysis']['confidence_score']}%
        - Words per Minute: {data['audio_analysis']['summary']['words_per_minute']}

        Video Analysis:
        - Eye Contact: {data['video_analysis']['metrics']['facial_expressions']['eye_contact']}%
        - Genuineness: {data['video_analysis']['metrics']['facial_expressions']['genuineness']}%
        - Posture Confidence: {data['video_analysis']['metrics']['posture']['upright_confident']}%
        - Engagement: {data['video_analysis']['metrics']['overall_energy']['engagement']}%

        Transcript:
        {data['transcript']}

        Please provide:
        1. Executive Summary
        2. Communication Skills Assessment
        3. Body Language Analysis
        4. Technical Knowledge Evaluation
        5. Overall Impression
        6. Recommendations for Improvement
        7. Final Score (0-100)
        """
        
        # Format content properly according to API requirements
        content = {
            "parts": [
                {"text": prompt_text}
            ]
        }
        
        # Generate report
        response = model.generate_content(content)
        
        if response.text:
            with open(output_file, 'w', encoding='utf-8') as file:
                file.write(response.text)
            print(f"Report successfully generated and saved to: {output_file}")
        else:
            print("Error: Empty response from Gemini")
            
    except Exception as e:
        print(f"Error generating report: {str(e)}")

if __name__ == "__main__":
    api_key = "AIzaSyB5tQYKNZM8TMkvTmnfwnRK7p0nwWDA0Yo"
    json_file = "report/candidate_1.json"
    output_file = "report/candidate_1_evaluation.txt"
    
    generate_report_with_gemini(json_file, output_file, api_key)
