import os
import requests
import re

TEAM_CUSTOMIZATIONS = {
    '21 CANNELLONI' : {
        'stadio': 'Merisacchio Stadium',
        'allenatore': 'Giovanni',
        'nomignolo': 'il principe ereditiero',
    },
    'L SGARRUPATI' : {
        'stadio': 'UK Arena',
        'allenatore': 'Antonio Pot',
        'direttore sportivo': 'Michele',
        'nomignolo': 'Sir Antonio D\'Inghilterra'
    },
    'SPARTAK J&N' : {
        'stadio': 'Malito Stadium',
        'allenatore': 'Luigi',
        'nomignolo': 'u putigaru'
    },
    'MANCHESTORS CITY' : {
        'stadio': 'Montebeltrano Stadium',
        'allenatore': 'Carmelo',
        'nomignolo': 'Orso'
    },
    'ESTATHEO' : {
        'stadio': 'Comunale di Grimaldi',
        'allenatore': 'Bruno',
        'nomignolo': 'Mister Bruno'
    },
    'FC CELL-TIC GLASGOW' : {
        'stadio': 'Vasciuta UPower',
        'allenatore': 'Gaetano',
        'nomignolo': 'Tano'
    },
    'A.S.DONALD DUCK' : {
        'stadio': 'Paperopoli Stadium',
        'allenatore': 'Antonio Pucci',
        'nomignolo': 'il professore'
    },
    'MBARCATURA © FC' : {
        'stadio': 'Stadio Mbarcatura',
        'allenatore': 'Riccardo',
        'nomignolo': 'Rick'
    },
    'EPICTOMINELLO' : {
        'stadio': 'BarberShop Stadium',
        'allenatore': 'Giovanni',
        'nomignolo': 'Mozzo'
    },
    'NK MAURIBOR'   : {
        'stadio': 'Peroni Arena',
        'allenatore': 'Mauro',
        'nomignolo': 'il catanzarese'
    },
  
 }

class PerplexityClient:
    def __init__(self):
        # Carica la chiave API da variabili ambiente
        self.api_key = os.getenv('PERPLEXITY_API_KEY')
        if not self.api_key:
            raise ValueError("PERPLEXITY_API_KEY non trovata nelle variabili d'ambiente")
        self.base_url = "https://api.perplexity.ai/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        print("✅ PerplexityClient inizializzato con successo")

    def generate_article(self, match_data):
        """
        Genera un articolo sportivo dettagliato usando i dati match_data.
        """
        try:
            prompt = self._build_prompt(match_data)
            payload = {
                "model": "sonar-pro",
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Sei un giornalista sportivo esperto di fantacalcio italiano. "
                            "Scrivi cronache complete, dettagliate e coinvolgenti. "
                            "NON interrompere mai gli articoli a metà. Completa ogni sezione e concludi con una frase definitiva. "
                            "Includi sempre i nomi dei giocatori forniti."
                        )
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "max_tokens": 1500,
                "temperature": 0.6,
                "stream": False
            }

            response = requests.post(self.base_url, json=payload, headers=self.headers, timeout=45)
            response.raise_for_status()

            result = response.json()
            content = result['choices'][0]['message']['content'].strip()
            content = re.sub(r"^\s*```(?:html)?\s*", "", content, flags=re.IGNORECASE)
            content = re.sub(r"\s*```\s*$", "", content).strip()

            print(f"✅ Articolo generato - lunghezza: {len(content)} caratteri")
            return content

        except requests.exceptions.RequestException as req_err:
            print(f"❌ Errore nella chiamata API: {req_err}")
            return self._fallback_article(match_data, f"Errore API: {req_err}")
        except Exception as e:
            print(f"💥 Errore inatteso: {e}")
            return self._fallback_article(match_data, str(e))

    def _build_prompt(self, match_data):
        """
        Costruisce prompt dettagliato e strutturato usando i dati di partita estratti.
        """
        home_team = match_data.get('home_team', 'Casa')
        away_team = match_data.get('away_team', 'Trasferta')

        # ✅ Usa il punteggio reale per determinare il risultato della partita
        real_home_score = match_data.get('home_score', 0)
        real_away_score = match_data.get('away_score', 0)

        # ✅ Usa il punteggio fantacalcio per il riepilogo
        try:
            fantasy_home_score = float(match_data.get('home_total', 0))
        except (ValueError, TypeError):
            fantasy_home_score = 0.0

        try:
            fantasy_away_score = float(match_data.get('away_total', 0))
        except (ValueError, TypeError):
            fantasy_away_score = 0.0
            
        gameweek = match_data.get('gameweek', 'N/A')

        players_info = self._format_players_info(match_data)

        summary = (
            f"**RIEPILOGO PARTITA DAL PARSER:** 🏠 Casa: {len(match_data.get('home_players', []))} titolari + "
            f"{len(match_data.get('home_bench', []))} panchina = {fantasy_home_score:.1f} punti totali ✈️ Trasferta: "
            f"{len(match_data.get('away_players', []))} titolari + {len(match_data.get('away_bench', []))} panchina = "
            f"{fantasy_away_score:.1f} punti totali"
        )

        # Determina il risultato basato sul punteggio reale
        if real_home_score > real_away_score:
            result = f"vittoria di {home_team}"
        elif real_away_score > real_home_score:
            result = f"vittoria di {away_team}"
        else:
            result = "pareggio"

        # Recupera personalizzazioni squadra
        home_custom = TEAM_CUSTOMIZATIONS.get(home_team, {})
        stadio_home = home_custom.get('stadio', 'Stadio Sconosciuto')
        allenatore_home = home_custom.get('allenatore', 'Allenatore Sconosciuto')
        nomignolo_home = home_custom.get('nomignolo', '')

        # Recupera personalizzazioni squadra ospite
        away_custom = TEAM_CUSTOMIZATIONS.get(away_team, {})
        stadio_away = away_custom.get('stadio', 'Stadio Sconosciuto')
        allenatore_away = away_custom.get('allenatore', 'Allenatore Sconosciuto')
        nomignolo_away = away_custom.get('nomignolo', '')
        # Istruzioni fondamentali per l'AI
        base_instructions = (
            f"Sei un giornalista sportivo esperto di fantacalcio italiano. "
            f"Scrivi articoli che non superino i 2000 caratteri. "
            f"Devi scrivere un articolo di cronaca sportiva usando ESCLUSIVAMENTE i dati reali che ti fornirò. "
            f"Enfatizza nomi, punteggi e statistiche e scrivili sempre in grassetto"
            f"Segui rigidamente la struttura HTML e le sezioni che ti indico. "
            f"NON inventare mai nomi, punteggi o formazioni. "
            f"Includi sempre i nomi dei giocatori forniti. L'articolo deve essere completo e non interrotto."
        )

        # Prompt con struttura rigida
        prompt = (
            f"{base_instructions}\n\n"
            f"DATI PARTITA:\n"
            f"PARTITA: {home_team} vs {away_team}\n"
            f"RISULTATO: {home_team} {real_home_score} - {real_away_score} {away_team}\n" # ✅ Usa punteggio reale qui
            f"GIORNATA: {gameweek}\n"
            f"RIEPILOGO STATISTICHE: {summary}\n"
            f"GIOCATORI E PUNTI FANTACALCIO REALI: {players_info}\n\n"
            f"STRUTTURA ARTICOLO (FORMATO HTML):\n\n"
            f"<h2>{home_team} vs {away_team}</h2>\n\n"
            f"<h3>Il Resoconto della Partita</h3>\n"
            f"<p>La partita si è giocata al <strong>{stadio_home}</strong>. Analizza il match e commenta il risultato finale di <strong>{real_home_score}</strong>-<strong>{real_away_score}</strong>.</p>\n\n"
            f"<p>Descrivi l'andamento del match. Commenta i punteggi totali e il risultato finale.</p>\n\n"
            f"<p>Commenta le scelte tattiche di <strong>{allenatore_home}</strong> e <strong>{allenatore_away}</strong>.Utilizza spesso ma non sempre <strong>{nomignolo_home}</strong> e ,<strong>{nomignolo_away}</strong>.</p>\n\n"
            f"<h3>I Migliori in Campo</h3>\n"
            f"<p>Analizza le prestazioni dei giocatori che hanno ottenuto i punteggi più alti (>8.0). Menziona almeno 3-4 nomi e il loro contributo.</p>\n\n"
            f"<h3>Le delusioni e i Flop</h3>\n"
            f"<p>Identifica i giocatori che hanno avuto un rendimento deludente (<6.0). Commenta il loro punteggio e come ha influenzato il risultato della loro squadra.</p>\n\n"
            f"<h3>Conclusione</h3>\n"
            f"<p>Riassumi i punti salienti della partita e le sue implicazioni per la classifica. Chiudi con una frase d'impatto.</p>"
        )

        return prompt

    def _format_players_info(self, match_data):
        """
        Format info giocatori dal dizionario match_data in testo leggibile per prompt.
        """
        lines = []

        def format_players(title, players):
            lines.append(f"\n**{title}:**")
            for p in players[:11]:  # solo titolari o primi 11
                name = p.get('name', 'Sconosciuto')
                role = p.get('role', 'N/A')

                fv = p.get('fanta_vote')
                if fv is None:
                    fv_str = "N/A"
                else:
                    fv_str = f"{fv:.1f}"

                v = p.get('vote')
                if v is None:
                    v_str = ""
                else:
                    v_str = f"{v:.1f}"

                played = p.get('played', False)
                if not played:
                    line = f"- {name} ({role}) - NON SCHIERATO"
                else:
                    line = f"- {name} ({role}) - Voto: {v_str}, FantaVoto: {fv_str}"

                lines.append(line)

        home_players = match_data.get('home_players', [])
        away_players = match_data.get('away_players', [])
        home_bench = match_data.get('home_bench', [])
        away_bench = match_data.get('away_bench', [])

        format_players(f"{match_data.get('home_team', 'Casa')} (TITOLARI)", home_players)
        format_players(f"{match_data.get('away_team', 'Trasferta')} (TITOLARI)", away_players)

        # Opzionale: aggiungi info panchina se vuoi
        # lines.append("\n**Panchina Casa:**")
        # for p in home_bench:
        #     lines.append(f"- {p.get('name', 'Sconosciuto')} ({p.get('role', 'N/A')})")

        # lines.append("\n**Panchina Trasferta:**")
        # for p in away_bench:
        #     lines.append(f"- {p.get('name', 'Sconosciuto')} ({p.get('role', 'N/A')})")

        # Migliori performance (opzionale)
        top_performers = match_data.get('player_analysis', {}).get('top_performers', [])
        if top_performers:
            lines.append("\n**Migliori prestazioni:**")
            for performer in top_performers[:5]:
                lines.append(f"- {performer}")

        return "\n".join(lines)

    def _fallback_article(self, match_data, error_message):
        """
        Genera un articolo semplice di fallback in caso di errore.
        """
        home_team = match_data.get('home_team', 'Casa')
        away_team = match_data.get('away_team', 'Trasferta')
        home_score = match_data.get('home_score', 0)
        away_score = match_data.get('away_score', 0)

        return (
            f"<h2>Resoconto partita {home_team} vs {away_team}</h2>"
            f"<p>Partita conclusa con risultato {home_score:.1f} - {away_score:.1f}.</p>"
            f"<p><em>Articolo generato automaticamente a causa di un errore: {error_message}</em></p>"
        )

