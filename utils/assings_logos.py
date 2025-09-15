# assign_logos.py
import os
from app import app
from extensions import db
from models import Team

def assign_logos_to_teams():
    """Assegna i percorsi dei loghi alle squadre esistenti nel database."""
    with app.app_context():
        print("🔍 Avvio assegnazione loghi...")
        
        # Percorso della cartella dei loghi
        logo_dir = os.path.join(app.root_path, 'static', 'images', 'logos')
        
        # Mappa i nomi dei file (senza estensione) a percorsi relativi
        logo_files = {
            os.path.splitext(f)[0].lower(): f'images/logos/{f}'
            for f in os.listdir(logo_dir)
            if os.path.isfile(os.path.join(logo_dir, f))
        }

        teams = Team.query.all()
        updated_count = 0

        for team in teams:
            # Pulisci il nome della squadra per confrontarlo con il nome del file
            team_name_clean = team.name.lower().replace(" ", "")
            
            # Cerca un file logo che corrisponda al nome della squadra
            found_logo = None
            if team_name_clean in logo_files:
                found_logo = logo_files[team_name_clean]
            # Gestisce nomi speciali, es. "roma"
            elif 'asroma' in team_name_clean:
                found_logo = logo_files.get('asroma')

            if found_logo:
                team.logo_url = found_logo
                db.session.add(team)
                updated_count += 1
                print(f"✅ Assegnato logo a: {team.name} -> {found_logo}")
            else:
                print(f"❌ Logo non trovato per: {team.name}")
        
        db.session.commit()
        print(f"\n🎉 Assegnazione completata. {updated_count} squadre aggiornate.")

if __name__ == "__main__":
    assign_logos_to_teams()