# Script per creare articoli di test - create_test_articles.py
from app_old import create_app
from models import db, Match, Article

app = create_app()

with app.app_context():
    matches_without_articles = Match.query.outerjoin(Article).filter(Article.id == None).all()
    
    print(f"Matches without articles: {len(matches_without_articles)}")
    
    for match in matches_without_articles:
        article_content = f"""
        <p>Analisi della partita tra <strong>{match.home_team}</strong> e <strong>{match.away_team}</strong> 
        terminata {match.home_score:.1f} - {match.away_score:.1f}.</p>
        
        <p>{'Una vittoria convincente per ' + match.away_team if match.away_score > match.home_score 
              else 'Una vittoria meritata per ' + match.home_team if match.home_score > match.away_score 
              else 'Un pareggio equilibrato'} nella giornata {match.gameweek}.</p>
        
        <p>Le formazioni hanno dato vita a uno spettacolo coinvolgente, con prestazioni individuali 
        di alto livello e scelte tattiche interessanti da parte di entrambi gli allenatori.</p>
        
        <p>Il match ha confermato la competitività del campionato, dove ogni punto può fare la differenza 
        per la classifica finale.</p>
        """
        
        article = Article(
            match_id=match.id,
            title=f"{match.home_team} vs {match.away_team}: Analisi Tattica",
            content=article_content
        )
        db.session.add(article)
        print(f"Created article for: {match.home_team} vs {match.away_team}")
    
    db.session.commit()
    print("Articles created successfully!")
