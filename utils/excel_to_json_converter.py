# utils/excel_to_json_structured.py
import pandas as pd
import json
import re
from pathlib import Path

class ExcelToJSONConverter:
    def __init__(self, excel_path):
        self.excel_path = excel_path
    
    def convert_to_structured_json(self, json_path=None):
        """Converte Excel in JSON strutturato per partite"""
        
        if json_path is None:
            json_path = str(Path(self.excel_path).with_suffix('_matches.json'))
        
        try:
            # Usa il tuo parser esistente per estrarre i dati
            from utils.excel_parser import ExcelParser
            parser = ExcelParser(self.excel_path)
            matches_data = parser.parse_matches()
            
            # Crea struttura JSON pulita
            json_structure = {
                "metadata": {
                    "source_file": str(Path(self.excel_path).name),
                    "total_matches": len(matches_data),
                    "conversion_date": pd.Timestamp.now().isoformat()
                },
                "matches": []
            }
            
            # Aggiungi ogni partita con struttura consistente
            for i, match in enumerate(matches_data):
                clean_match = {
                    "match_id": i + 1,
                    "home_team": match.get('home_team', ''),
                    "away_team": match.get('away_team', ''),
                    "home_total": float(match.get('home_total', 0)),
                    "away_total": float(match.get('away_total', 0)),
                    "home_formation": match.get('home_formation_code', ''),
                    "away_formation": match.get('away_formation_code', ''),
                    "home_players": len(match.get('home_players', [])),
                    "away_players": len(match.get('away_players', [])),
                    "modifiers": {
                        "home": match.get('home_modifiers', {}),
                        "away": match.get('away_modifiers', {})
                    }
                }
                json_structure["matches"].append(clean_match)
            
            # Salva JSON
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(json_structure, f, indent=2, ensure_ascii=False)
            
            print(f"✅ JSON strutturato creato: {json_path}")
            print(f"📊 Partite convertite: {len(matches_data)}")
            
            return json_path
            
        except Exception as e:
            print(f"❌ Errore conversione strutturata: {e}")
            raise
    
    def preview_json_structure(self):
        """Anteprima della struttura JSON senza salvare"""
        try:
            from utils.excel_parser import ExcelParser
            parser = ExcelParser(self.excel_path)
            matches_data = parser.parse_matches()
            
            if matches_data:
                sample_match = matches_data[0]
                print("📋 Struttura JSON preview:")
                print(json.dumps({
                    "metadata": {"total_matches": len(matches_data)},
                    "matches": [sample_match]
                }, indent=2, ensure_ascii=False, default=str))
            
        except Exception as e:
            print(f"❌ Errore preview: {e}")
