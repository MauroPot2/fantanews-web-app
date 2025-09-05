# utils/excel_parser.py - VERSIONE DEFINITIVA MIGLIORATA
import pandas as pd
from datetime import datetime
import re

class ExcelParser:
    def __init__(self, file_path):
        self.file_path = file_path

    def _find_formazioni_sheet(self):
        """
        Trova il foglio Excel che contiene le formazioni.
        Se non trova nomi significativi, ritorna il primo foglio.
        """
        try:
            # Leggi tutti i nomi dei fogli
            xl = pd.ExcelFile(self.file_path)
            possible_names = ['formazioni', 'formazione', 'lineup', 'lineups', 'squadre']
            for sheet in xl.sheet_names:
                if any(name.lower() in sheet.lower() for name in possible_names):
                    return sheet
            # Se nessuno corrisponde, usa il primo
            return xl.sheet_names
        except Exception as e:
            print(f"❌ Errore nel trovare il foglio formazioni: {e}")
            return None

    
    def parse_matches(self):
        """Estrae tutti i dati completi delle partite dal file Excel"""
        sheet_name = self._find_formazioni_sheet()
        print(f"🔍 Parsing foglio: {sheet_name}")
        df = pd.read_excel(self.file_path, sheet_name=sheet_name)

        matches = []
        current_row = 0
        
        print(f"📊 Dimensioni DataFrame: {len(df)} righe x {len(df.columns)} colonne")
        
        while current_row < len(df):
            if (pd.notna(df.iloc[current_row, 0]) and  
                pd.notna(df.iloc[current_row, 6]) and  
                pd.notna(df.iloc[current_row, 5]) and  
                '-' in str(df.iloc[current_row, 5])):   
                
                print(f"🎯 Trovata partita alla riga {current_row}: {df.iloc[current_row, 0]} vs {df.iloc[current_row, 6]} ({df.iloc[current_row, 5]})")
                
                match_data = self._parse_single_match(df, current_row)
                if match_data:
                    matches.append(match_data)
                    current_row = match_data['next_row']
                else:
                    current_row += 1
            else:
                current_row += 1
        
        print(f"✅ Totale partite estratte: {len(matches)}")
        return matches
    
    def _parse_single_match(self, df, start_row):
        """Estrae i dati di una singola partita con ricerca avanzata"""
        try:
            home_team = df.iloc[start_row, 0]         
            away_team = df.iloc[start_row, 6]         
            score_str = str(df.iloc[start_row, 5])    
            
            print(f"   📋 Parsing: {home_team} vs {away_team} (Score: {score_str})")
            
            # Parse del risultato
            score_match = re.search(r'(\d+)\s*[-]\s*(\d+)', score_str)
            if score_match:
                home_score = int(score_match.group(1))
                away_score = int(score_match.group(2))
            else:
                home_score = away_score = 0
            
            # Moduli tattici
            current_row = start_row + 1
            home_formation_code = df.iloc[current_row, 0] if pd.notna(df.iloc[current_row, 0]) else ""
            away_formation_code = df.iloc[current_row, 6] if pd.notna(df.iloc[current_row, 6]) else ""
            
            current_row += 1
            
            # Inizializza variabili
            home_players = []
            away_players = []
            home_bench = []
            away_bench = []
            home_modifiers = {}
            away_modifiers = {}
            home_total = None
            away_total = None
            home_timestamp = ""
            away_timestamp = ""
            is_bench_section = False
            
            # ✅ RICERCA AVANZATA DEI TOTALI
            total_search_range = min(start_row + 50, len(df))  # Cerca in 50 righe
            
            # ✅ PARSING MIGLIORATO DEL CONTENUTO
            while current_row < total_search_range:
                row = df.iloc[current_row]
                
                # Controlla sezione panchina
                if (pd.notna(row.iloc[0]) and str(row.iloc[0]).strip().lower() == 'panchina') or \
                   (pd.notna(row.iloc[6]) and str(row.iloc[6]).strip().lower() == 'panchina'):
                    is_bench_section = True
                    print(f"      🔄 Sezione panchina iniziata alla riga {current_row}")
                    current_row += 1
                    continue
                
                # ✅ RICERCA TOTALI MIGLIORATA: Cerca in TUTTE le colonne
                found_total = False
                for col_idx in range(len(row)):
                    if pd.notna(row.iloc[col_idx]) and isinstance(row.iloc[col_idx], str):
                        cell_value = str(row.iloc[col_idx]).strip()
                        
                        if 'TOTALE:' in cell_value:
                            total_str = cell_value.replace('TOTALE:', '').replace(',', '.').strip()
                            try:
                                total_value = float(total_str)
                                
                                # ✅ LOGICA MIGLIORATA: Determina casa/trasferta
                                if col_idx <= 5:  # Colonne A-F = Casa
                                    if home_total is None:
                                        home_total = total_value
                                        print(f"      🏠 Totale casa trovato in colonna {col_idx}: {home_total}")
                                        found_total = True
                                else:  # Colonne G+ = Trasferta
                                    if away_total is None:
                                        away_total = total_value
                                        print(f"      ✈️ Totale trasferta trovato in colonna {col_idx}: {away_total}")
                                        found_total = True
                                        
                            except ValueError:
                                continue
                
                if found_total:
                    current_row += 1
                    continue
                
                # Parse modificatori
                if pd.notna(row.iloc[0]) and 'Modificatore' in str(row.iloc[0]):
                    modifier_name = str(row.iloc[0])
                    modifier_value = row.iloc[4] if pd.notna(row.iloc[4]) else 0
                    home_modifiers[modifier_name] = modifier_value
                    print(f"      🏠 Modificatore casa: {modifier_name} = {modifier_value}")
                    current_row += 1
                    continue
                
                if pd.notna(row.iloc[6]) and 'Modificatore' in str(row.iloc[6]):
                    modifier_name = str(row.iloc[6])
                    modifier_value = row.iloc[10] if pd.notna(row.iloc[10]) else 0
                    away_modifiers[modifier_name] = modifier_value
                    print(f"      ✈️ Modificatore trasferta: {modifier_name} = {modifier_value}")
                    current_row += 1
                    continue
                
                # Timestamp
                if pd.notna(row.iloc[0]) and 'Inserita via app' in str(row.iloc[0]):
                    home_timestamp = str(row.iloc[0])
                    current_row += 1
                    continue
                
                if pd.notna(row.iloc[6]) and 'Inserita via app' in str(row.iloc[6]):
                    away_timestamp = str(row.iloc[6])
                    current_row += 1
                    continue
                
                # Controllo fine partita
                if (pd.isna(row.iloc[0]) and pd.isna(row.iloc[1]) and pd.isna(row.iloc[2]) and
                    pd.isna(row.iloc[6]) and pd.isna(row.iloc[7]) and pd.isna(row.iloc[8])):
                    # Se abbiamo trovato entrambi i totali, usciamo
                    if home_total is not None and away_total is not None:
                        print(f"      🏁 Fine partita alla riga {current_row} - totali trovati")
                        break
                
                # ✅ PARSE GIOCATORI DETTAGLIATO
                home_player = self._parse_player_advanced(row, 0, 1, 3, 4)      
                away_player = self._parse_player_advanced(row, 6, 7, 9, 10)     
                
                if home_player:
                    if is_bench_section:
                        home_bench.append(home_player)
                    else:
                        home_players.append(home_player)
                
                if away_player:
                    if is_bench_section:
                        away_bench.append(away_player)
                    else:
                        away_players.append(away_player)
                
                current_row += 1
            
            # ✅ FALLBACK per totali mancanti
            if home_total is None:
                home_total = float(home_score) if home_score > 0 else 66.0  # Default fantacalcio
                print(f"      ⚠️ Totale casa non trovato, uso fallback: {home_total}")
                
            if away_total is None:
                away_total = float(away_score) if away_score > 0 else 66.0  # Default fantacalcio
                print(f"      ⚠️ Totale trasferta non trovato, uso fallback: {away_total}")
            
            # ✅ ANALISI GIOCATORI per AI
            player_analysis = self._analyze_players(home_players, away_players, home_bench, away_bench)
            
            home_player_names = [p['name'] for p in home_players]
            home_bench_names = [p['name'] for p in home_bench]
        
            # Log finale
            print(f"      📊 Risultato parsing:")
            print(f"Casa: titolari ({', '.join(home_player_names)}) + panchina ({', '.join(home_bench_names)}) = {home_total}")
            print(f"         ✈️ Trasferta: {len(away_players)} titolari + {len(away_bench)} panchina = {away_total}")
            print(f"         ⭐ Migliori: {player_analysis['top_performers'][:3]}")
            
            match_data = {
                'home_team': home_team,
                'away_team': away_team,
                'home_score': home_score,
                'away_score': away_score,
                'home_formation_code': home_formation_code,
                'away_formation_code': away_formation_code,
                'home_players': home_players,
                'away_players': away_players,
                'home_bench': home_bench,
                'away_bench': away_bench,
                'home_modifiers': home_modifiers,
                'away_modifiers': away_modifiers,
                'home_total': home_total,
                'away_total': away_total,
                'home_timestamp': home_timestamp,
                'away_timestamp': away_timestamp,
                'player_analysis': player_analysis,  # ✅ NUOVA SEZIONE
                'next_row': current_row + 1
            }

            return match_data
        
        except Exception as e:
            print(f"❌ Errore nel parsing della partita alla riga {start_row}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _parse_player_advanced(self, row, role_col, name_col, vote_col, fanta_col):
        """Parse avanzato giocatore con analisi performance"""
        try:
            if pd.isna(row.iloc[role_col]) or pd.isna(row.iloc[name_col]):
                return None
            
            role = str(row.iloc[role_col]).strip()
            name = str(row.iloc[name_col]).strip()
            
            # Filtra nomi non validi
            if len(name) < 2 or name.lower() in ['panchina', 'modificatore', 'totale', 'inserita']:
                return None
            
            # ✅ PARSE VOTI DETTAGLIATO
            vote = None
            fanta_vote = None
            
            if pd.notna(row.iloc[vote_col]) and str(row.iloc[vote_col]) != '-':
                try:
                    vote = float(str(row.iloc[vote_col]).replace(',', '.'))
                except:
                    vote = None
            
            if pd.notna(row.iloc[fanta_col]) and str(row.iloc[fanta_col]) != '-':
                try:
                    fanta_vote = float(str(row.iloc[fanta_col]).replace(',', '.'))
                except:
                    fanta_vote = None
            
            # ✅ ANALISI PERFORMANCE per AI
            performance_category = self._categorize_performance(vote, fanta_vote)
            
            return {
                'role': role,
                'name': name,
                'vote': vote,
                'fanta_vote': fanta_vote,
                'played': vote is not None and fanta_vote is not None,
                'performance_category': performance_category,  # ✅ NUOVO
                'is_top_performer': fanta_vote and fanta_vote >= 8.0,
                'is_poor_performer': fanta_vote and fanta_vote <= 5.0,
                'has_bonus': fanta_vote and vote and (fanta_vote - vote) >= 2,
                'has_malus': fanta_vote and vote and (vote - fanta_vote) >= 2
            }
        
        except Exception as e:
            return None
    
    def _categorize_performance(self, vote, fanta_vote):
        """Categorizza la performance del giocatore"""
        if not vote or not fanta_vote:
            return "not_played"
        
        if fanta_vote >= 8.0:
            return "excellent"
        elif fanta_vote >= 7.0:
            return "good"
        elif fanta_vote >= 6.0:
            return "average"
        elif fanta_vote >= 5.0:
            return "poor"
        else:
            return "very_poor"
    
    def _analyze_players(self, home_players, away_players, home_bench, away_bench):
        """Analizza tutti i giocatori per creare insights per l'AI"""
        all_players = home_players + away_players + home_bench + away_bench
        played_players = [p for p in all_players if p['played']]
        
        # ✅ TOP PERFORMERS
        top_performers = []
        if played_players:
            sorted_players = sorted(played_players, key=lambda x: x['fanta_vote'] or 0, reverse=True)
            top_performers = [
                f"{p['name']} ({p['role']}) - {p['fanta_vote']:.1f}" 
                for p in sorted_players[:5] if p['fanta_vote']
            ]
        
        # ✅ POOR PERFORMERS  
        poor_performers = []
        if played_players:
            poor_sorted = sorted(played_players, key=lambda x: x['fanta_vote'] or 10, reverse=False)
            poor_performers = [
                f"{p['name']} ({p['role']}) - {p['fanta_vote']:.1f}" 
                for p in poor_sorted[:3] if p['fanta_vote'] and p['fanta_vote'] <= 5.5
            ]
        
        # ✅ BONUS/MALUS
        bonus_players = [p for p in played_players if p.get('has_bonus', False)]
        malus_players = [p for p in played_players if p.get('has_malus', False)]
        
        return {
            'top_performers': top_performers,
            'poor_performers': poor_performers,
            'bonus_players': [f"{p['name']} (+{p['fanta_vote'] - p['vote']:.1f})" for p in bonus_players[:3]],
            'malus_players': [f"{p['name']} ({p['fanta_vote'] - p['vote']:.1f})" for p in malus_players[:3]],
            'total_players': len(all_players),
            'played_count': len(played_players)
        }
    
    
    def get_match_statistics(self, matches):
        """Genera statistiche complete per tutti i match"""
        stats = {
            'total_matches': len(matches),
            'total_goals': sum(match['home_score'] + match['away_score'] for match in matches),
            'avg_goals_per_match': 0,
            'highest_scoring_match': None,
            'best_performers': [],
            'worst_performers': [],
            'most_used_formations': {},
            'team_performances': {}
        }
        
        if len(matches) > 0:
            stats['avg_goals_per_match'] = stats['total_goals'] / len(matches)
            
            # Trova la partita con più gol
            max_goals = 0
            for match in matches:
                total_goals = match['home_score'] + match['away_score']
                if total_goals > max_goals:
                    max_goals = total_goals
                    stats['highest_scoring_match'] = f"{match['home_team']} {match['home_score']}-{match['away_score']} {match['away_team']}"
            
            # Analizza performance dei giocatori
            all_players = []
            for match in matches:
                all_players.extend(match['home_players'] + match['away_players'])
                all_players.extend(match['home_bench'] + match['away_bench'])
            
            # Migliori e peggiori performance
            played_players = [p for p in all_players if p['played'] and p['fanta_vote'] is not None]
            if played_players:
                played_players.sort(key=lambda x: x['fanta_vote'], reverse=True)
                stats['best_performers'] = played_players[:5]
                stats['worst_performers'] = played_players[-5:]
            
            # Formazioni più utilizzate
            formations = []
            for match in matches:
                if match['home_formation_code']:
                    formations.append(match['home_formation_code'])
                if match['away_formation_code']:
                    formations.append(match['away_formation_code'])
            
            for formation in formations:
                clean_formation = re.sub(r'\([^)]*\)', '', formation).strip()
                if clean_formation:
                    stats['most_used_formations'][clean_formation] = stats['most_used_formations'].get(clean_formation, 0) + 1
            
            # Performance delle squadre
            for match in matches:
                home_team = match['home_team']
                away_team = match['away_team']
                
                if home_team not in stats['team_performances']:
                    stats['team_performances'][home_team] = {'points': 0, 'matches': 0}
                if away_team not in stats['team_performances']:
                    stats['team_performances'][away_team] = {'points': 0, 'matches': 0}
                
                stats['team_performances'][home_team]['points'] += match['home_total']
                stats['team_performances'][home_team]['matches'] += 1
                stats['team_performances'][away_team]['points'] += match['away_total']
                stats['team_performances'][away_team]['matches'] += 1
        
        return stats
    
    def export_to_csv(self, matches, filename='fantacalcio_data.csv'):
        """Esporta tutti i dati in formato CSV per analisi"""
        all_data = []
        
        for match in matches:
            base_match_data = {
                'home_team': match['home_team'],
                'away_team': match['away_team'],
                'home_score': match['home_score'],
                'away_score': match['away_score'],
                'home_total': match['home_total'],
                'away_total': match['away_total'],
                'home_formation': match['home_formation_code'],
                'away_formation': match['away_formation_code']
            }
            
            # Aggiungi dati giocatori casa
            for player in match['home_players'] + match['home_bench']:
                row = base_match_data.copy()
                row.update({
                    'team_type': 'home',
                    'player_section': 'bench' if player in match['home_bench'] else 'starter',
                    'player_name': player['name'],
                    'player_role': player['role'],
                    'player_vote': player['vote'],
                    'player_fanta_vote': player['fanta_vote'],
                    'player_played': player['played']
                })
                all_data.append(row)
            
            # Aggiungi dati giocatori trasferta
            for player in match['away_players'] + match['away_bench']:
                row = base_match_data.copy()
                row.update({
                    'team_type': 'away',
                    'player_section': 'bench' if player in match['away_bench'] else 'starter',
                    'player_name': player['name'],
                    'player_role': player['role'],
                    'player_vote': player['vote'],
                    'player_fanta_vote': player['fanta_vote'],
                    'player_played': player['played']
                })
                all_data.append(row)
        
        df = pd.DataFrame(all_data)
        df.to_csv(filename, index=False, encoding='utf-8')
        return filename

# Test del parser
if __name__ == "__main__":
    parser = ExcelParser('Formazioni_fantagrimaldi-storico-2022-23_1_giornata.xlsx')
    
    try:
        matches = parser.parse_matches()
        print(f"\n🎯 RISULTATI FINALI:")
        print(f"Partite trovate: {len(matches)}")
        
        for i, match in enumerate(matches):
            print(f"\n{i+1}. {match['home_team']} vs {match['away_team']}")
            print(f"   Risultato: {match['home_score']}-{match['away_score']}")
            print(f"   Totali: {match['home_total']:.1f} - {match['away_total']:.1f}")
            print(f"   Giocatori casa: {len(match['home_players'])} + {len(match['home_bench'])} panchina")
            print(f"   Giocatori trasferta: {len(match['away_players'])} + {len(match['away_bench'])} panchina")
        
    except Exception as e:
        print(f"❌ Errore durante il test: {e}")
        import traceback
        traceback.print_exc()
