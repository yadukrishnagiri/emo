import os
import json
import chromadb
from chromadb.utils import embedding_functions
import hashlib
from datetime import datetime

class SpeechAnalysisCache:
    """
    Class to cache speech analysis results using ChromaDB to reduce API usage.
    """
    def __init__(self, persist_directory="./chroma_db"):
        """Initialize the ChromaDB client and collection"""
        # Create directory if it doesn't exist
        os.makedirs(persist_directory, exist_ok=True)
        
        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(path=persist_directory)
        
        # Use the default embedding function
        self.embedding_func = embedding_functions.DefaultEmbeddingFunction()
        
        # Create or get collection for speech analysis
        self.collection = self.client.get_or_create_collection(
            name="speech_analysis",
            embedding_function=self.embedding_func,
            metadata={"description": "Cache of speech analysis results"}
        )
        
        print(f"ChromaDB initialized with collection: speech_analysis")
    
    def generate_hash(self, audio_data):
        """Generate a unique hash for the audio data"""
        # If audio_data is a file path, read the file
        if isinstance(audio_data, str) and os.path.isfile(audio_data):
            with open(audio_data, "rb") as f:
                # Read first 1MB of file for hashing (for efficiency)
                content = f.read(1024 * 1024)
                return hashlib.md5(content).hexdigest()
        
        # If it's binary data
        elif isinstance(audio_data, bytes):
            return hashlib.md5(audio_data).hexdigest()
        
        # If it's a string (like transcript)
        elif isinstance(audio_data, str):
            return hashlib.md5(audio_data.encode('utf-8')).hexdigest()
        
        else:
            raise ValueError("Invalid audio data format for hashing")
    
    def get_cached_analysis(self, audio_path=None, transcript=None):
        """
        Try to get cached analysis results based on audio file or transcript
        
        Returns:
            analysis_data (dict): The cached analysis data or None if not found
        """
        try:
            # Generate hash from audio file or transcript
            if audio_path:
                doc_id = self.generate_hash(audio_path)
            elif transcript:
                doc_id = self.generate_hash(transcript)
            else:
                return None
            
            # Query the collection
            results = self.collection.get(
                ids=[doc_id],
                include=["metadatas", "documents"]
            )
            
            # Check if we got results
            if results and results['ids'] and len(results['ids']) > 0:
                # Return cached analysis
                cached_data = json.loads(results['documents'][0])
                print(f"✓ Retrieved cached analysis from ChromaDB (ID: {doc_id[:8]}...)")
                return cached_data
            
            print(f"No cached analysis found for ID: {doc_id[:8]}...")
            return None
            
        except Exception as e:
            print(f"Error retrieving from cache: {str(e)}")
            return None
    
    def cache_analysis(self, analysis_data, audio_path=None, transcript=None):
        """
        Cache the speech analysis results
        
        Args:
            analysis_data (dict): The analysis data to cache
            audio_path (str): Path to the audio file (optional)
            transcript (str): Transcript text (optional)
        """
        try:
            # One of audio_path or transcript must be provided
            if not audio_path and not transcript:
                raise ValueError("Either audio_path or transcript must be provided")
            
            # Generate hash from audio file or transcript
            if audio_path:
                doc_id = self.generate_hash(audio_path)
                text_for_embedding = os.path.basename(audio_path)
            else:
                doc_id = self.generate_hash(transcript)
                # Use first 1000 chars of transcript for embedding
                text_for_embedding = transcript[:1000]
            
            # Convert analysis data to string
            analysis_json = json.dumps(analysis_data)
            
            # Store in collection
            self.collection.upsert(
                ids=[doc_id],
                documents=[analysis_json],
                metadatas=[{
                    "cached_date": datetime.now().isoformat(),
                    "audio_filename": os.path.basename(audio_path) if audio_path else None,
                    "transcript_length": len(transcript) if transcript else None
                }]
            )
            
            print(f"✓ Cached analysis in ChromaDB (ID: {doc_id[:8]}...)")
            return True
            
        except Exception as e:
            print(f"Error caching analysis: {str(e)}")
            return False 