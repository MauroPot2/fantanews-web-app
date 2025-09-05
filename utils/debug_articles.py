# Debug script - crea file debug_articles.py
from app_old import create_app
from models import db, Match, Article

app = create_app()

with app.app_context():
    matches = Match.query.all()
    articles = Article.query.all()
    
    print(f"Matches in database: {len(matches)}")
    print(f"Articles in database: {len(articles)}")
    
    for match in matches:
        article = Article.query.filter_by(match_id=match.id).first()
        print(f"Match {match.id}: {match.home_team} vs {match.away_team} - Article: {'YES' if article else 'NO'}")
