import json
from ai_report_generator import AIReportGenerator

def generate_report_with_gemini(json_file, output_file, api_key):
    try:
        # Use our AI report generator with ChromaDB caching
        report_generator = AIReportGenerator(api_key)
        
        # Read JSON file
        with open(json_file, 'r') as file:
            data = json.load(file)
        
        # Generate report using the cached generator
        evaluation_text, score = report_generator.generate_report(data)
        
        if evaluation_text:
            with open(output_file, 'w', encoding='utf-8') as file:
                file.write(evaluation_text)
            print(f"Report successfully generated and saved to: {output_file}")
            
            # Also save score separately
            score_file = output_file.replace("_evaluation.txt", "_score.txt")
            with open(score_file, 'w') as file:
                file.write(f"Final Score: {score}/100")
            print(f"Score saved to: {score_file}")
        else:
            print("Error: Empty response from Gemini")
            
    except Exception as e:
        print(f"Error generating report: {str(e)}")

if __name__ == "__main__":
    api_key = "AIzaSyB5tQYKNZM8TMkvTmnfwnRK7p0nwWDA0Yo"
    json_file = "report/candidate_1.json"
    output_file = "report/candidate_1_evaluation.txt"
    
    generate_report_with_gemini(json_file, output_file, api_key)