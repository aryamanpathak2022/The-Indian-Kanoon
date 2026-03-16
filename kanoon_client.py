import requests
import config

class KanoonClient:
    def __init__(self):
        self.base_url = config.BASE_URL
        self.headers = {
            "Authorization": f"Token {config.API_TOKEN}",
            "Accept": "application/json"
        }

    def search_documents(self, query, doc_type=None):
        """
        Search for documents. 
        doc_type: filter by type - 'judgments' (default), 'acts', 'rules', 'all'
        """
        try:
            resp = requests.post(f"{self.base_url}/search/", headers=self.headers, params={"formInput": query})
            if resp.status_code == 200:
                data = resp.json()
                docs = data.get('docs', [])
                
                # Filter to show only judgments (default behavior)
                if doc_type == 'judgments' or doc_type is None:
                    docs = [doc for doc in docs if self._is_judgment(doc)]
                elif doc_type == 'acts':
                    docs = [doc for doc in docs if not self._is_judgment(doc)]
                # 'all' returns everything
                
                return {'docs': docs, 'total': len(docs)}
            return {}
        except Exception as e:
            print(f"Search error: {e}")
            return {}

    def _is_judgment(self, doc):
        """Check if the document is a judgment (court case) vs act/rules"""
        # Judgments typically have specific patterns
        title = doc.get('title', '').lower()
        doc_type = doc.get('docType', '').lower()
        
        # Exclude acts, rules, bare acts, sections
        exclude_keywords = ['act', 'rule', 'section', 'regulation', 'code', 'ordinance']
        
        for keyword in exclude_keywords:
            if keyword in title or keyword in doc_type:
                return False
        
        # If it looks like a case (with parties like "vs", "v.", or case numbers)
        case_indicators = [' vs ', ' v. ', ' vs. ', 'appellant', 'respondent', 'petitioner']
        for indicator in case_indicators:
            if indicator in title:
                return True
        
        # Default to judgment if uncertain (safer for privacy)
        return True

    def get_document(self, doc_id):
        try:
            resp = requests.post(f"{self.base_url}/doc/{doc_id}/", headers=self.headers)
            return resp.json() if resp.status_code == 200 else {}
        except Exception as e:
            print(f"Get document error: {e}")
            return {}