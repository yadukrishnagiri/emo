import os
import json
import tkinter as tk
from tkinter import filedialog
from tkinter import messagebox
from content_validator import ContentValidator

def main():
    """
    Standalone script to demonstrate content validation functionality
    """
    # Initialize the content validator
    validator = ContentValidator()
    
    # Create a basic UI
    root = tk.Tk()
    root.title("Interview Video Validator")
    root.geometry("600x500")
    
    # Header
    header_label = tk.Label(
        root, 
        text="Interview Content Validator", 
        font=("Arial", 16, "bold")
    )
    header_label.pack(pady=10)
    
    info_label = tk.Label(
        root,
        text="Select a video file to validate whether it contains an interview",
        wraplength=500
    )
    info_label.pack(pady=5)
    
    # File selection
    file_frame = tk.Frame(root)
    file_frame.pack(pady=10, fill=tk.X, padx=20)
    
    file_path_var = tk.StringVar()
    file_entry = tk.Entry(file_frame, textvariable=file_path_var, width=50)
    file_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
    
    def select_file():
        file_path = filedialog.askopenfilename(
            title="Select Video File",
            filetypes=[("Video files", "*.mp4 *.avi *.mkv *.mov")]
        )
        if file_path:
            file_path_var.set(file_path)
    
    browse_button = tk.Button(file_frame, text="Browse", command=select_file)
    browse_button.pack(side=tk.RIGHT, padx=5)
    
    # API Key for transcript (optional)
    api_frame = tk.Frame(root)
    api_frame.pack(pady=5, fill=tk.X, padx=20)
    
    api_label = tk.Label(api_frame, text="AssemblyAI API Key (optional):")
    api_label.pack(side=tk.LEFT, padx=5)
    
    api_key_var = tk.StringVar(value="3af788588a404358aa3edf58900d1fcc")  # Default key
    api_entry = tk.Entry(api_frame, textvariable=api_key_var, width=40)
    api_entry.pack(side=tk.RIGHT, padx=5, fill=tk.X, expand=True)
    
    # Results display
    results_frame = tk.Frame(root, relief=tk.GROOVE, borderwidth=2)
    results_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
    
    results_label = tk.Label(results_frame, text="Validation Results:", font=("Arial", 12, "bold"))
    results_label.pack(anchor=tk.W, padx=10, pady=5)
    
    results_text = tk.Text(results_frame, height=15, width=70, wrap=tk.WORD)
    results_text.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)
    
    # Progress and status display
    status_var = tk.StringVar(value="Ready")
    status_label = tk.Label(root, textvariable=status_var, font=("Arial", 10, "italic"))
    status_label.pack(pady=5)
    
    # Validation function
    def validate_video():
        file_path = file_path_var.get()
        if not file_path or not os.path.exists(file_path):
            messagebox.showerror("Error", "Please select a valid video file")
            return
            
        # Clear previous results
        results_text.delete(1.0, tk.END)
        status_var.set("Validating video...")
        root.update()
        
        try:
            # First validate without transcript
            status_var.set("Checking video content (without transcript)...")
            root.update()
            
            validation_results = validator.validate_video(
                file_path, 
                audio_path=None,
                api_key=None
            )
            
            # Display initial results
            results_text.insert(tk.END, "INITIAL VALIDATION (Video Only):\n")
            results_text.insert(tk.END, f"Valid interview: {validation_results['is_valid']}\n")
            results_text.insert(tk.END, f"Confidence: {validation_results['confidence']}%\n")
            results_text.insert(tk.END, f"Reason: {validation_results['reason']}\n\n")
            
            # Display detailed checks
            for check_name, check_results in validation_results['checks'].items():
                results_text.insert(tk.END, f"{check_name.upper()}: {check_results['passed']}\n")
                results_text.insert(tk.END, f"Score: {check_results['score']}%\n")
                results_text.insert(tk.END, f"Details: {check_results['details']}\n\n")
            
            # Check if user provided API key for transcript analysis
            api_key = api_key_var.get().strip()
            if api_key:
                status_var.set("Performing transcript analysis...")
                root.update()
                
                try:
                    # Create temporary audio file
                    import tempfile
                    import subprocess
                    
                    temp_dir = tempfile.mkdtemp()
                    audio_path = os.path.join(temp_dir, "temp_audio.mp3")
                    
                    # Extract audio
                    status_var.set("Extracting audio for transcript analysis...")
                    root.update()
                    
                    subprocess.run([
                        'ffmpeg', '-i', file_path, 
                        '-t', '15', '-q:a', '0', '-map', 'a', 
                        audio_path
                    ], capture_output=True)
                    
                    if os.path.exists(audio_path):
                        # Perform validation with transcript
                        status_var.set("Analyzing transcript content...")
                        root.update()
                        
                        full_validation = validator.validate_video(
                            file_path, 
                            audio_path=audio_path,
                            api_key=api_key
                        )
                        
                        # Display full results with transcript
                        results_text.insert(tk.END, "FULL VALIDATION (With Transcript):\n")
                        results_text.insert(tk.END, f"Valid interview: {full_validation['is_valid']}\n")
                        results_text.insert(tk.END, f"Confidence: {full_validation['confidence']}%\n")
                        results_text.insert(tk.END, f"Reason: {full_validation['reason']}\n\n")
                        
                        # Display transcript check
                        if 'transcript_content' in full_validation['checks']:
                            transcript_check = full_validation['checks']['transcript_content']
                            results_text.insert(tk.END, "TRANSCRIPT ANALYSIS:\n")
                            results_text.insert(tk.END, f"Passed: {transcript_check['passed']}\n")
                            results_text.insert(tk.END, f"Score: {transcript_check['score']}%\n")
                            results_text.insert(tk.END, f"Details: {transcript_check['details']}\n")
                            
                            if 'transcript_preview' in transcript_check:
                                results_text.insert(tk.END, f"\nTranscript Preview:\n{transcript_check['transcript_preview']}\n")
                    
                    # Clean up temp files
                    try:
                        os.remove(audio_path)
                        os.rmdir(temp_dir)
                    except:
                        pass
                        
                except Exception as e:
                    results_text.insert(tk.END, f"\nError during transcript analysis: {str(e)}\n")
            
            # Set final status
            if validation_results['is_valid']:
                status_var.set("Validation complete: Valid interview content detected")
            else:
                status_var.set("Validation complete: This may not be interview content")
                
        except Exception as e:
            results_text.insert(tk.END, f"Error during validation: {str(e)}")
            status_var.set("Error during validation")
    
    # Validation button
    validate_button = tk.Button(
        root, 
        text="Validate Video", 
        command=validate_video,
        bg="#4CAF50",
        fg="white",
        font=("Arial", 12),
        padx=20
    )
    validate_button.pack(pady=10)
    
    # Start the application
    root.mainloop()

if __name__ == "__main__":
    main() 