from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig
from presidio_analyzer.nlp_engine import SpacyNlpEngine
import spacy
import re

# Load spaCy model
import sys
import os
venv_python = os.path.join(os.path.dirname(sys.executable), 'python')

try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    import subprocess
    subprocess.run([venv_python, "-m", "spacy", "download", "en_core_web_sm"], check=True)
    nlp = spacy.load("en_core_web_sm")

# Create custom NLP engine with loaded model
class LoadedSpacyNlpEngine(SpacyNlpEngine):
    def __init__(self, loaded_spacy_model):
        super().__init__()
        self.nlp = {"en": loaded_spacy_model}

loaded_nlp_engine = LoadedSpacyNlpEngine(nlp)

class SmartMasker:
    def __init__(self):
        self.analyzer = AnalyzerEngine(nlp_engine=loaded_nlp_engine)
        self.anonymizer = AnonymizerEngine()
        
        # Keywords that indicate a person is a victim or family member
        self.sensitive_context_words = [
            "victim", "deceased", "prosecutrix", "minor", "child", "survivor",
            "wife of", "son of", "daughter of", "husband of", "mother of", "father of",
            "complainant", "informant", "appellant", "respondent", "petitioner"
        ]
        
        # Track all names that have been masked for consistent replacement
        self.name_mapping = {}  # original_name -> masked_value
        
    def reset_mapping(self):
        """Reset the name mapping for a new document"""
        self.name_mapping = {}

    def _is_sensitive_context(self, text, start, end, window=100):
        """
        Checks if any sensitive keyword exists near the detected entity.
        Increased window size for better context detection.
        """
        snippet_start = max(0, start - window)
        snippet_end = min(len(text), end + window)
        snippet = text[snippet_start:snippet_end].lower()

        for word in self.sensitive_context_words:
            if word in snippet:
                return True
        return False
    
    def _extract_name_from_context(self, text, start, end, window=30):
        """Extract the actual name from the context"""
        snippet_start = max(0, start - window)
        snippet_end = min(len(text), end + window)
        snippet = text[snippet_start:snippet_end]
        
        # Look for patterns like "Name (victim)" or "Name (deceased)"
        patterns = [
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*\([^)]*(?:victim|deceased|minor|child|survivor|wife|son|daughter|husband|mother|father|complainant|informant)[^)]*\)',
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+-\s*(?:victim|deceased|minor|child|survivor)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, snippet, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        # Return the entity text if no pattern found
        return text[start:end].strip()

    def mask_victims_and_family(self, text):
        """Main function to mask sensitive information with consistent mapping"""
        if not text:
            return "", {}
        
        self.reset_mapping()
        
        # Initialize counters
        analysis = {
            "total_masked": 0,
            "victim_family_count": 0,
            "phone_count": 0,
            "email_count": 0,
            "location_count": 0,
            "original_length": len(text),
            "masked_length": 0,
            "reduction_percentage": 0
        }
        
        # First pass: Find ALL people and determine which to mask
        results = self.analyzer.analyze(
            text=text,
            entities=["PERSON", "PHONE_NUMBER", "EMAIL_ADDRESS", "LOCATION"],
            language='en'
        )
        
        # Sort results by position to process in order
        results = sorted(results, key=lambda x: x.start)
        
        # Build a list of entities to mask
        entities_to_mask = []
        person_entities = []
        
        for res in results:
            if res.entity_type in ["PHONE_NUMBER", "EMAIL_ADDRESS", "LOCATION"]:
                entities_to_mask.append(res)
                if res.entity_type == "PHONE_NUMBER":
                    analysis["phone_count"] += 1
                elif res.entity_type == "EMAIL_ADDRESS":
                    analysis["email_count"] += 1
                elif res.entity_type == "LOCATION":
                    analysis["location_count"] += 1
            elif res.entity_type == "PERSON":
                person_entities.append(res)
        
        # Second pass: For PERSON entities, check context more thoroughly
        # Also check if same name appears elsewhere with/without context
        for res in person_entities:
            # Check if this person should be masked based on context
            if self._is_sensitive_context(text, res.start, res.end):
                # Extract the name for consistent mapping
                actual_name = self._extract_name_from_context(text, res.start, res.end)
                entities_to_mask.append(res)
                analysis["victim_family_count"] += 1
        
        # Third pass: Check for consistent masking
        # If a name is masked in one place, mask it everywhere it appears
        if entities_to_mask:
            # Get all person names that were masked
            masked_names = set()
            for res in entities_to_mask:
                if res.entity_type == "PERSON":
                    actual_name = self._extract_name_from_context(text, res.start, res.end)
                    if actual_name and len(actual_name) > 2:  # Skip very short names
                        masked_names.add(actual_name.lower())
            
            # Now scan the entire text for any occurrences of these names
            all_results = self.analyzer.analyze(text=text, entities=["PERSON"], language='en')
            for res in all_results:
                actual_name = self._extract_name_from_context(text, res.start, res.end)
                if actual_name and actual_name.lower() in masked_names:
                    # Add this entity to mask if not already in list
                    if res not in entities_to_mask:
                        entities_to_mask.append(res)
        
        # Sort entities by position (reverse order for replacement)
        entities_to_mask = sorted(entities_to_mask, key=lambda x: x.start, reverse=True)
        
        # Create masked text with consistent name mapping
        masked_text = text
        for res in entities_to_mask:
            if res.entity_type == "PERSON":
                actual_name = self._extract_name_from_context(text, res.start, res.end)
                
                # Check if we've already assigned a mask for this name
                if actual_name.lower() in self.name_mapping:
                    replacement = self.name_mapping[actual_name.lower()]
                else:
                    # Assign a new consistent mask
                    mask_num = len(self.name_mapping) + 1
                    replacement = f"[VICTIM/FAMILY_{mask_num}]"
                    self.name_mapping[actual_name.lower()] = replacement
                
                # Replace in text (handle both with and without context)
                original_name = text[res.start:res.end]
                masked_text = masked_text[:res.start] + replacement + masked_text[res.end:]
                
            elif res.entity_type == "PHONE_NUMBER":
                masked_text = masked_text[:res.start] + "[PHONE]" + masked_text[res.end:]
            elif res.entity_type == "EMAIL_ADDRESS":
                masked_text = masked_text[:res.start] + "[EMAIL]" + masked_text[res.end:]
            elif res.entity_type == "LOCATION":
                masked_text = masked_text[:res.start] + "[LOC]" + masked_text[res.end:]
        
        # Final cleanup: replace any remaining sensitive names that weren't caught
        # Check for names appearing without context after being masked elsewhere
        for original_mask, replacement in self.name_mapping.items():
            # Find all occurrences of this name in original text
            pattern = re.compile(re.escape(original_mask), re.IGNORECASE)
            matches = list(pattern.finditer(text))
            if len(matches) > 1:  # If name appears multiple times
                for match in matches:
                    # Check if this occurrence is NOT in entities_to_mask
                    is_masked = False
                    for res in entities_to_mask:
                        if res.start == match.start() and res.entity_type == "PERSON":
                            is_masked = True
                            break
                    if not is_masked:
                        # Mask this occurrence too
                        masked_text = masked_text[:match.start()] + replacement + masked_text[match.end():]
        
        # Update analysis
        analysis["total_masked"] = len(entities_to_mask)
        analysis["masked_length"] = len(masked_text)
        if analysis["original_length"] > 0:
            analysis["reduction_percentage"] = int(round(
                (1 - analysis["masked_length"] / analysis["original_length"]) * 100
            ))
        
        return masked_text, analysis