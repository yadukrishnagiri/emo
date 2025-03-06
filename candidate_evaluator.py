import os
import json
import google.generativeai as genai
from datetime import datetime
import tkinter as tk
from tkinter import ttk

class CandidateEvaluator:
    def __init__(self, api_key):
        # Configure Gemini API
        genai.configure(api_key=api_key)
        
        # Use the correct model name
        try:
            self.model = genai.GenerativeModel('gemini-pro')
            # Test the model
            response = self.model.generate_content("Test")
            print("API connection successful")
        except Exception as e:
            print(f"Error initializing API: {str(e)}")
            self.model = None
        
        # Candidate basic info
        self.candidate_info = {
            "name": "",
            "education": "",
            "current_role": "",
            "key_skills": [],
            "career_goals": ""
        }
        
        # Evaluation parameters
        self.coherence_metrics = {
            "topic_adherence": 0,
            "logical_flow": 0,
            "depth_of_knowledge": 0,
            "clarity_of_expression": 0
        }
        
    def get_candidate_info_gui(self):
        try:
            print("Opening candidate info window...")
            root = tk.Tk()
            root.title("Candidate Information")
            root.geometry("500x600+300+200")  # Position window at x=300, y=200
            root.attributes('-topmost', True)  # Keep window on top
            root.deiconify()  # Ensure window is not minimized
            print("Window should be visible now...")
            
            print("Setting up GUI elements...")  # Debug print
            # Style
            style = ttk.Style()
            style.configure('TLabel', padding=5)
            style.configure('TEntry', padding=5)
            style.configure('TButton', padding=5)
            
            # Create form
            frame = ttk.Frame(root, padding="10")
            frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
            
            # Name
            ttk.Label(frame, text="Full Name:").grid(row=0, column=0, sticky=tk.W)
            name_var = tk.StringVar()
            ttk.Entry(frame, textvariable=name_var, width=40).grid(row=0, column=1, pady=5)
            
            # Education
            ttk.Label(frame, text="Educational Qualification:").grid(row=1, column=0, sticky=tk.W)
            edu_var = tk.StringVar()
            ttk.Entry(frame, textvariable=edu_var, width=40).grid(row=1, column=1, pady=5)
            
            # Current Role
            ttk.Label(frame, text="Current/Previous Job Role:").grid(row=2, column=0, sticky=tk.W)
            role_var = tk.StringVar()
            ttk.Entry(frame, textvariable=role_var, width=40).grid(row=2, column=1, pady=5)
            
            # Key Skills
            ttk.Label(frame, text="Key Skills (comma separated):").grid(row=3, column=0, sticky=tk.W)
            skills_var = tk.StringVar()
            ttk.Entry(frame, textvariable=skills_var, width=40).grid(row=3, column=1, pady=5)
            
            # Career Goals
            ttk.Label(frame, text="Career Goals:").grid(row=4, column=0, sticky=tk.W)
            goals_text = tk.Text(frame, height=4, width=40)
            goals_text.grid(row=4, column=1, pady=5)
            
            def save_info():
                self.candidate_info["name"] = name_var.get()
                self.candidate_info["education"] = edu_var.get()
                self.candidate_info["current_role"] = role_var.get()
                self.candidate_info["key_skills"] = [s.strip() for s in skills_var.get().split(",")]
                self.candidate_info["career_goals"] = goals_text.get("1.0", tk.END).strip()
                root.destroy()
            
            ttk.Button(frame, text="Save", command=save_info).grid(row=5, column=1, pady=20)
            
            root.mainloop()
        except Exception as e:
            print(f"Error creating GUI: {str(e)}")
            # Provide fallback to command line input
            self.get_candidate_info_cli()
        
    def read_candidate_files(self, candidate_num):
        base_path = r"C:\Users\yaduk\OneDrive\Desktop\Projects\major\emo"
        
        # Read both txt and json reports
        report_txt_path = os.path.join(base_path, 'report', f'candidate_{candidate_num}.txt')
        report_json_path = os.path.join(base_path, 'report', f'candidate_{candidate_num}.json')
        transcript_path = os.path.join(base_path, 'transcript', f'candidate_{candidate_num}.txt')
        
        try:
            # Read text report
            with open(report_txt_path, 'r', encoding='utf-8') as f:
                report_txt_content = f.read()
            
            # Read JSON report for detailed metrics
            with open(report_json_path, 'r', encoding='utf-8') as f:
                report_json_content = json.load(f)
            
            # Read transcript
            with open(transcript_path, 'r', encoding='utf-8') as f:
                transcript_content = f.read()
                
            return report_txt_content, report_json_content, transcript_content
        except Exception as e:
            print(f"Error reading files: {str(e)}")
            return None, None, None
            
    def analyze_topic_coherence(self, transcript):
        prompt = f"""
        Analyze the following interview transcript for topic coherence and expertise.
        Candidate Background:
        - Name: {self.candidate_info['name']}
        - Education: {self.candidate_info['education']}
        - Current Role: {self.candidate_info['current_role']}
        - Key Skills: {', '.join(self.candidate_info['key_skills'])}
        - Career Goals: {self.candidate_info['career_goals']}
        
        Transcript:
        {transcript}
        
        Please evaluate:
        1. How well did the candidate stay on topic?
        2. Was there logical flow in their responses?
        3. Did they demonstrate depth of knowledge in their field?
        4. How clear was their expression of ideas?
        5. How well do their responses align with their stated career goals?
        6. Did they effectively demonstrate their key skills?
        
        Provide specific examples and a score (0-100) for each aspect.
        """
        
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            print(f"Error analyzing topic coherence: {str(e)}")
            return None
            
    def generate_comprehensive_evaluation(self, report_txt, report_json, transcript):
        prompt = f"""
        Provide a comprehensive evaluation for:
        
        Candidate Background:
        - Name: {self.candidate_info['name']}
        - Education: {self.candidate_info['education']}
        - Current Role: {self.candidate_info['current_role']}
        - Key Skills: {', '.join(self.candidate_info['key_skills'])}
        - Career Goals: {self.candidate_info['career_goals']}
        
        Report Content:
        {report_txt}
        
        Detailed Metrics:
        {json.dumps(report_json, indent=2)}
        
        Transcript:
        {transcript}
        
        Please analyze:
        1. Technical competency relative to their background
        2. Communication skills and professional presence
        3. Problem-solving ability and analytical thinking
        4. Cultural fit and team compatibility
        5. Alignment between skills and career goals
        6. Areas for improvement
        7. Professional development recommendations
        8. Overall suitability for the role
        
        Provide specific examples and actionable feedback.
        """
        
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            print(f"Error generating evaluation: {str(e)}")
            return None
            
    def generate_evaluation_report(self, candidate_num):
        print("Starting evaluation process...")
        
        # Check if model is available
        if not self.model:
            print("Error: AI model not available. Cannot generate analysis.")
            return
        
        # Get candidate info
        self.get_candidate_info_gui()
        print("Candidate info collected...")  # Debug print
        
        # Read files
        report_txt, report_json, transcript = self.read_candidate_files(candidate_num)
        if not report_txt or not report_json or not transcript:
            return
            
        # Analyze topic coherence
        coherence_analysis = self.analyze_topic_coherence(transcript)
        
        # Generate comprehensive evaluation
        comprehensive_eval = self.generate_comprehensive_evaluation(report_txt, report_json, transcript)
        
        # Create final report
        final_report = f"""
        Candidate Evaluation Report
        =========================
        Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        
        Candidate Information
        -------------------
        Name: {self.candidate_info['name']}
        Educational Qualification: {self.candidate_info['education']}
        Current/Previous Role: {self.candidate_info['current_role']}
        Key Skills: {', '.join(self.candidate_info['key_skills'])}
        Career Goals: {self.candidate_info['career_goals']}
        
        Topic Coherence Analysis
        ----------------------
        {coherence_analysis}
        
        Comprehensive Evaluation
        ----------------------
        {comprehensive_eval}
        """
        
        # Save the report
        base_path = r"C:\Users\yaduk\OneDrive\Desktop\Projects\major\emo"
        eval_path = os.path.join(base_path, 'evaluations')
        os.makedirs(eval_path, exist_ok=True)
        
        output_path = os.path.join(eval_path, f'candidate_{candidate_num}_evaluation.txt')
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(final_report)
            
        print(f"Evaluation report saved: {output_path}")

def main():
    # Initialize with your Gemini API key
    api_key = "AIzaSyCAi9rvhNqgY86QPcHxE4tCjjIZC-kWjWM"
    evaluator = CandidateEvaluator(api_key)
    
    try:
        candidate_num = input("Enter candidate number to evaluate: ")
        evaluator.generate_evaluation_report(candidate_num)
    except Exception as e:
        print(f"Error in evaluation: {str(e)}")

if __name__ == "__main__":
    main() 