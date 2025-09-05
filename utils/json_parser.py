# utils/json_parser.py
import json
from typing import List, Dict

class JSONParser:
    def __init__(self, json_path: str):
        self.json_path = json_path
    
    def parse_matches(self) -> List[Dict]:
        """Parse del file JSON per l'app"""
        try:
            with open(self.json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Estrai matches dalla struttura
            if 'matches' in data:
                matches = data['matches']
            else:
                # Fallback se JSON è lista diretta
                matches = data if isinstance(data, list) else []
            
            # Converti in formato atteso dall'app
            processed_matches = []
            for match in matches:
                processed_match = {
                    'home_team': match.get('home_team', ''),
                    'away_team': match.get('away_team', ''),
                    'home_total': float(match.get('home_total', 0)),
                    'away_total': float(match.get('away_total', 0)),
                    'home_formation_code': match.get('home_formation', ''),
                    'away_formation_code': match.get('away_formation', ''),
                    # Aggiungi altri campi necessari
                }
                processed_matches.append(processed_match)
            
            print(f"✅ Caricati {len(processed_matches)} match dal JSON")
            return processed_matches
            
        except Exception as e:
            print(f"❌ Errore parsing JSON: {e}")
            raise
