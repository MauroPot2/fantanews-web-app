# test_new_model.py
from utils.perplexity_client import PerplexityClient

def test_real_api():
    client = PerplexityClient()
    
    test_match = {
        'home_team': 'FC CELL-TIC GLASGOW',
        'away_team': 'EPICTOMINELLO',
        'home_score': 79.0,
        'away_score': 66.5
    }
    
    print("🧪 Test con nuovo modello...")
    article = client.generate_article(test_match)
    
    print("\n📝 Articolo Perplexity:")
    print("=" * 60)
    print(article)
    print("=" * 60)
    
    # Controlla se è fallback o vero articolo Perplexity
    if "Articolo generato automaticamente" in article:
        print("❌ È ancora un fallback, controlla l'API")
    else:
        print("✅ Articolo vero di Perplexity!")

if __name__ == "__main__":
    test_real_api()
