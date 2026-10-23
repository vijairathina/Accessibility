"""
Example usage of the PDF Tagging Application
"""

from main import PDFTaggingPipeline
import os

# Example 1: Basic usage with environment variable
def example_basic():
    """Basic usage with API key from environment."""
    pipeline = PDFTaggingPipeline()
    result = pipeline.process_pdf("input.pdf", "output.pdf")
    print("Processing complete!")
    print(f"Tagged {result['tag_metadata']['total_tags']} blocks")

# Example 2: Usage with explicit API key
def example_with_api_key():
    """Usage with explicit API key."""
    api_key = "your-api-key-here"
    pipeline = PDFTaggingPipeline(gemini_api_key=api_key)
    result = pipeline.process_pdf("input.pdf", "output.pdf")
    print("Processing complete!")

# Example 3: Access individual components
def example_components():
    """Use individual components separately."""
    from pdf_extractor import PDFExtractor
    from pre_ai_processor import PreAIProcessor
    from gemini_classifier import GeminiClassifier
    from validator import ClassificationValidator
    from pdf_tagger import PDFTagger
    
    # Extract content
    extractor = PDFExtractor()
    content = extractor.extract_content("input.pdf")
    
    # Structure blocks
    processor = PreAIProcessor()
    structured = processor.structure_blocks(content)
    
    # Classify with AI
    classifier = GeminiClassifier()
    classified = classifier.classify_blocks(structured)
    
    # Validate
    validator = ClassificationValidator()
    validated = validator.validate(classified['classified_blocks'])
    
    # Tag PDF
    tagger = PDFTagger()
    tag_metadata = tagger.inject_tags(
        "input.pdf",
        validated['validated_blocks'],
        "output.pdf"
    )
    
    print(f"Tagged {tag_metadata['total_tags']} blocks")

if __name__ == "__main__":
    # Make sure GEMINI_API_KEY is set in .env file
    if os.getenv("GEMINI_API_KEY"):
        example_basic()
    else:
        print("Please set GEMINI_API_KEY in .env file first")
