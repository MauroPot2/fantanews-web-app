# utils/calculate_standings.py
from collections import defaultdict
from models import Team, Match
from extensions import db

def calculate_standings():
    """Calcola la classifica del campionato con statistiche aggiuntive."""
    try:
        matches = Match.query.all()

        if not matches:
            return {
                'standings': [],
                'best_attack': None,
                'best_defense': None,
                'most_wins': None
            }

        team_stats = defaultdict(lambda: {
            'points': 0, 'matches_played': 0, 'wins': 0, 'draws': 0, 'losses': 0,
            'goals_for': 0.0, 'goals_against': 0.0
        })

        for match in matches:
            home_team_name = match.home_team
            away_team_name = match.away_team

            # Calcola i gol fantacalcio
            home_goals = max(0, (match.home_score - 60) // 6) if match.home_score is not None else 0
            away_goals = max(0, (match.away_score - 60) // 6) if match.away_score is not None else 0

            # Aggiorna statistiche
            team_stats[home_team_name]['matches_played'] += 1
            team_stats[away_team_name]['matches_played'] += 1

            team_stats[home_team_name]['goals_for'] += home_goals
            team_stats[home_team_name]['goals_against'] += away_goals
            team_stats[away_team_name]['goals_for'] += away_goals
            team_stats[away_team_name]['goals_against'] += home_goals

            # Assegna punti, vittorie, pareggi e sconfitte
            if home_goals > away_goals:
                team_stats[home_team_name]['wins'] += 1
                team_stats[home_team_name]['points'] += 3
                team_stats[away_team_name]['losses'] += 1
            elif away_goals > home_goals:
                team_stats[away_team_name]['wins'] += 1
                team_stats[away_team_name]['points'] += 3
                team_stats[home_team_name]['losses'] += 1
            else:
                team_stats[home_team_name]['draws'] += 1
                team_stats[home_team_name]['points'] += 1
                team_stats[away_team_name]['draws'] += 1
                team_stats[away_team_name]['points'] += 1
        
        # Mappa i nomi delle squadre agli oggetti Team per i dettagli nel template
        teams_map = {t.name: t for t in Team.query.all()}
        
        standings = []
        for name, stats in team_stats.items():
            team = teams_map.get(name)
            if team:
                standings.append({
                    'id': team.id,
                    'name': team.name,
                    'points': stats['points'],
                    'matches_played': stats['matches_played'],
                    'wins': stats['wins'],
                    'draws': stats['draws'],
                    'losses': stats['losses'],
                    'goals_for': stats['goals_for'],
                    'goals_against': stats['goals_against'],
                    'goal_difference': stats['goals_for'] - stats['goals_against'],
                    'avg_points_for': stats['goals_for'] / stats['matches_played'] if stats['matches_played'] > 0 else 0,
                })
        
        # Ordina la classifica
        standings.sort(key=lambda x: (x['points'], x['goal_difference'], x['goals_for']), reverse=True)

        # Trova le statistiche extra
        best_attack = max(standings, key=lambda x: x['goals_for']) if standings else None
        best_defense = min(standings, key=lambda x: x['goals_against']) if standings else None
        most_wins = max(standings, key=lambda x: x['wins']) if standings else None
        
        return {
            'standings': standings,
            'best_attack': best_attack,
            'best_defense': best_defense,
            'most_wins': most_wins
        }

    except Exception as e:
        print(f"❌ Errore calcolo classifica: {e}")
        return {
            'standings': [],
            'best_attack': None,
            'best_defense': None,
            'most_wins': None
        }