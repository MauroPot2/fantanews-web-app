# utils/calculate_standings.py - Versione corretta
from models import db, Team, Match

def calculate_standings():
    """Calcola classifica con gestione errori migliorata"""
    
    try:
        matches = Match.query.all()
        
        if not matches:
            print("⚠️ Nessuna partita trovata per calcolare la classifica")
            return []
        
        print(f"📊 Calcolando classifica per {len(matches)} partite")
        
        # Reset tutte le squadre esistenti
        teams = Team.query.all()
        for team in teams:
            team.points = 0
            team.matches_played = 0
            team.wins = 0
            team.draws = 0
            team.losses = 0
            team.goals_for = 0
            team.goals_against = 0
        
        # Processa ogni partita
        for match in matches:
            print(f"  🏆 Processing: {match.home_team} vs {match.away_team}")
            
            # ✅ FIX: Trova o crea squadra casa
            home_team = Team.query.filter_by(name=match.home_team).first()
            if not home_team:
                home_team = Team(
                    name=match.home_team,
                    points=0, matches_played=0, wins=0, draws=0, losses=0,
                    goals_for=0, goals_against=0
                )
                db.session.add(home_team)
                db.session.flush()
                print(f"    ➕ Creata squadra: {match.home_team}")
            
            # ✅ FIX: Trova o crea squadra trasferta
            away_team = Team.query.filter_by(name=match.away_team).first()
            if not away_team:
                away_team = Team(
                    name=match.away_team,
                    points=0, matches_played=0, wins=0, draws=0, losses=0,
                    goals_for=0, goals_against=0
                )
                db.session.add(away_team)
                db.session.flush()
                print(f"    ➕ Creata squadra: {match.away_team}")
            
            # Converti punteggi fantacalcio in gol (esempio: 66+ = 1 gol, +6 = +1 gol)
            home_goals = max(0, int((match.home_score - 60) / 6))
            away_goals = max(0, int((match.away_score - 60) / 6))
            
            # Aggiorna statistiche
            home_team.matches_played += 1
            away_team.matches_played += 1
            home_team.goals_for += home_goals
            home_team.goals_against += away_goals
            away_team.goals_for += away_goals
            away_team.goals_against += home_goals
            
            # Assegna punti
            if home_goals > away_goals:
                home_team.wins += 1
                home_team.points += 3
                away_team.losses += 1
            elif away_goals > home_goals:
                away_team.wins += 1
                away_team.points += 3
                home_team.losses += 1
            else:
                home_team.draws += 1
                away_team.draws += 1
                home_team.points += 1
                away_team.points += 1
        
        db.session.commit()
        
        # Ritorna classifica ordinata
        standings = Team.query.order_by(
            Team.points.desc(),
            (Team.goals_for - Team.goals_against).desc(),
            Team.goals_for.desc()
        ).all()
        
        print(f"✅ Classifica calcolata: {len(standings)} squadre")
        return standings
        
    except Exception as e:
        print(f"❌ Errore calcolo classifica: {e}")
        db.session.rollback()
        return []
