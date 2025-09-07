from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from utils.fantacalcio_utils import points_to_goals
from extensions import db  # Importa l'istanza db da extensions.py

class Season(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    current = db.Column(db.Boolean, default=False)

# models.py - aggiorna il modello Team
class Team(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    points = db.Column(db.Integer, default=0, nullable=False)  # Aggiungi nullable=False
    matches_played = db.Column(db.Integer, default=0, nullable=False)
    wins = db.Column(db.Integer, default=0, nullable=False)
    draws = db.Column(db.Integer, default=0, nullable=False)
    losses = db.Column(db.Integer, default=0, nullable=False)
    goals_for = db.Column(db.Integer, default=0, nullable=False)
    goals_against = db.Column(db.Integer, default=0, nullable=False)
    points_for = db.Column(db.Float, default=0.0, nullable=False)
    points_against = db.Column(db.Float, default=0.0, nullable=False)
    
    # Aggiunge la relazione con la classe Player
    players = db.relationship('Player', backref='team', lazy=True)

    @property
    def goal_difference(self):
        goals_for = self.goals_for or 0.0  # Gestisci None
        goals_against = self.goals_against or 0.0
        return goals_for - goals_against

    @property
    def avg_points_for(self):
        """Media punti fantacalcio per partita"""
        if self.matches_played > 0:
            return self.points_for / self.matches_played
        return 0.0
    
    @property
    def avg_goals_for(self):
        """Media gol per partita"""
        if self.matches_played > 0:
            return self.goals_for / self.matches_played
        return 0.0

class Match(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    season_id = db.Column(db.Integer, db.ForeignKey('season.id'))
    gameweek = db.Column(db.Integer, nullable=False)
    home_team = db.Column(db.String(100), nullable=False)
    away_team = db.Column(db.String(100), nullable=False)
    home_score = db.Column(db.Float, nullable=False)  # Punteggio fantacalcio
    away_score = db.Column(db.Float, nullable=False)  # Punteggio fantacalcio
    date_played = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    # Proprietà calcolate per i gol
    @property
    def home_goals(self):
        return points_to_goals(self.home_score)
    
    @property
    def away_goals(self):
        return points_to_goals(self.away_score)
    
    @property
    def result_description(self):
        if self.home_goals > self.away_goals:
            return f"Vittoria {self.home_team}"
        elif self.away_goals > self.home_goals:
            return f"Vittoria {self.away_team}"
        else:
            return "Pareggio"
    
    @property
    def is_high_scoring(self):
        """Partita con molti gol (6+ gol totali)"""
        return (self.home_goals + self.away_goals) >= 6

class Article(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey('match.id'))
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Player(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)
    goals = db.Column(db.Integer, default=0)
    assists = db.Column(db.Integer, default=0)
    clean_sheets = db.Column(db.Integer, default=0)
    is_goalkeeper = db.Column(db.Boolean, default=False)
    
class PlayerStat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey('player.id'))
    match_id = db.Column(db.Integer, db.ForeignKey('match.id'))
    is_starter = db.Column(db.Boolean, default=True)
    vote = db.Column(db.Float, nullable=True)  # Voto in pagella
    fanta_vote = db.Column(db.Float, nullable=True)
    goals = db.Column(db.Integer, default=0)
    assists = db.Column(db.Integer, default=0)
    clean_sheet = db.Column(db.Integer, default=0)

    # Relazioni con i modelli Player e Match
    player = db.relationship('Player', backref=db.backref('stats', lazy=True))
    match = db.relationship('Match', backref=db.backref('player_stats', lazy=True))
    
    def __repr__(self):
        return f"<PlayerStat {self.player.name} - Match: {self.match.gameweek} - Fantavoto: {self.fantavoto}>"
