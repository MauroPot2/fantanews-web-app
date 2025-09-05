# delete_old_articles.py
from app_old import create_app
from models import db, Article

app = create_app()

with app.app_context():
    # Cancella tutti gli articoli esistenti
    articles_count = Article.query.count()
    Article.query.delete()
    db.session.commit()
    
    print(f"✅ Cancellati {articles_count} articoli obsoleti")
    print("💡 Ora ricarica i tabellini per generare nuovi articoli con Perplexity")
