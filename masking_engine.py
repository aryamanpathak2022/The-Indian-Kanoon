from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig
import spacy

# Load spaCy model
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    import subprocess
    subprocess.run(["python", "-m", "spacy", "download", "en_core_web_sm"], check=True)
    nlp = spacy.load("en_core_web_sm")

class SmartMasker:
    def __init__(self):
        self.analyzer = AnalyzerEngine(nlp=nlp)
        self.anonymizer = AnonymizerEngine()
        
        # Keywords that indicate a person is a victim or family member
        self.sensitive_context_words = [
            "victim", "deceased", "prosecutrix", "minor", "child", "survivor",
            "wife of", "son of", "daughter of", "husband of", "mother of", "father of",
            "complainant", "informant"
        ]

    def _is_sensitive_context(self, text, start, end, window=50):
        """
        Checks if any sensitive keyword exists near the detected entity.
        """
        # Define the window of text to check (e.g., 50 chars before and after)
        snippet_start = max(0, start - window)
        snippet_end = min(len(text), end + window)
        snippet = text[snippet_start:snippet_end].lower()

        # Check if any trigger word is in this snippet
        for word in self.sensitive_context_words:
            if word in snippet:
                return True
        return False

    def mask_victims_and_family(self, text):
        if not text:
            return ""

        # 1. Analyze: Find ALL people
        results = self.analyzer.analyze(
            text=text,
            entities=["PERSON", "PHONE_NUMBER", "EMAIL_ADDRESS", "LOCATION"],
            language='en'
        )

        # 2. Filter: Keep ONLY entities that are likely victims/family
        sensitive_results = []
        for res in results:
            # Always mask Phone/Email/Address regardless of context
            if res.entity_type in ["PHONE_NUMBER", "EMAIL_ADDRESS", "LOCATION"]:
                sensitive_results.append(res)
                continue
            
            # For PERSON, check context
            if res.entity_type == "PERSON":
                if self._is_sensitive_context(text, res.start, res.end):
                    sensitive_results.append(res)
                else:
                    # It's likely a Judge, Lawyer, or Accused -> Ignore
                    pass

        # 3. Anonymize: Mask only the filtered list
        anonymized_result = self.anonymizer.anonymize(
            text=text,
            analyzer_results=sensitive_results,
            operators={
                "PERSON": OperatorConfig("replace", {"new_value": "[VICTIM/FAMILY]"}),
                "PHONE_NUMBER": OperatorConfig("replace", {"new_value": "[PHONE]"}),
                "EMAIL_ADDRESS": OperatorConfig("replace", {"new_value": "[EMAIL]"}),
                "LOCATION": OperatorConfig("replace", {"new_value": "[LOC]"}),
            }
        )

        return anonymized_result.text