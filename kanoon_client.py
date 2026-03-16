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
            # Use GET request with params as per API
            resp = requests.get(f"{self.base_url}/search/", headers=self.headers, params={"formInput": query})
            
            if resp.status_code == 200:
                data = resp.json()
                docs = data.get('docs', [])
                
                # Filter to show only judgments (default behavior)
                # doctype 1000 = judgments
                if doc_type == 'judgments' or doc_type is None:
                    docs = [doc for doc in docs if doc.get('doctype') == 1000]
                elif doc_type == 'acts':
                    docs = [doc for doc in docs if doc.get('doctype') != 1000]
                # 'all' returns everything
                
                return {'docs': docs, 'total': len(docs)}
            else:
                print(f"API returned status: {resp.status_code}")
                return {'docs': [], 'total': 0}
        except Exception as e:
            print(f"Search error: {e}")
            return {'docs': [], 'total': 0}

    def get_document(self, doc_id):
        try:
            resp = requests.get(f"{self.base_url}/doc/{doc_id}/", headers=self.headers)
            return resp.json() if resp.status_code == 200 else {}
        except Exception as e:
            print(f"Get document error: {e}")
            return {}