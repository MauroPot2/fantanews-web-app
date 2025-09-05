import os
import requests

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

            # Post-processa per assicurare che l'articolo sia completo
            content = self._post_process(content, match_data)

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
        Costruisce prompt dettagliato usando i dati di partita estratti.
        """
        home_team = match_data.get('home_team', 'Casa')
        away_team = match_data.get('away_team', 'Trasferta')
        home_score = match_data.get('home_total', 0)
        away_score = match_data.get('away_total', 0)
        gameweek = match_data.get('gameweek', 'N/A')

        players_info = self._format_players_info(match_data)

        summary = (
            f"**RIEPILOGO PARTITA DAL PARSER:** 🏠 Casa: {len(match_data.get('home_players', []))} titolari + "
            f"{len(match_data.get('home_bench', []))} panchina = {home_score:.1f} punti totali ✈️ Trasferta: "
            f"{len(match_data.get('away_players', []))} titolari + {len(match_data.get('away_bench', []))} panchina = "
            f"{away_score:.1f} punti totali"
        )

        if home_score > away_score:
            result = f"vittoria di {home_team}"
        elif away_score > home_score:
            result = f"vittoria di {away_team}"
        else:
            result = "pareggio"

        prompt = (
            f"Scrivi un articolo di cronaca sportiva usando ESCLUSIVAMENTE i dati reali estratti dal parser Excel:\n"
            f"**PARTITA**: {home_team} {home_score:.1f} - {away_score:.1f} {away_team}\n"
            f"**GIORNATA**: {gameweek}\n"
            f"**RISULTATO**: {result}\n"
            f"{summary}\n"
            f"**GIOCATORI REALI ESTRATTI DAL PARSER (USA SOLO QUESTI NOMI):**\n"
            f"{players_info}\n"
            f"**ISTRUZIONI FONDAMENTALI**:\n"
            f"- Usa esclusivamente i nomi dei giocatori elencati sopra\n"
            f"- Ogni giocatore ha il punteggio fantacalcio reale estratto dal file Excel\n"
            f"- Non inventare mai nomi di fantasia\n"
            f"- Menziona almeno 8-10 giocatori per nome nell'articolo\n"
            f"- Analizza le prestazioni basandoti sui punteggi reali mostrati\n"
            f"- I giocatori con punteggio >8.0 hanno fatto ottime prestazioni\n"
            f"- I giocatori con punteggio <6.0 hanno fatto prestazioni sottotono\n"
            f"**REQUISITI ARTICOLO:**\n"
            f"- Lunghezza: 800-1000 parole\n"
            f"- Tono: giornalistico sportivo, coinvolgente\n"
            f"- Lingua: italiano\n"
            f"Scrivi l'articolo completo in HTML usando i dati reali del parser."
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
                fv = p.get('fanta_vote', 0)
                v = p.get('vote', 0)
                line = f"- {name} ({role}): {fv:.1f} punti fantacalcio"
                if v and v != fv:
                    line += f" (voto {v:.1f})"
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

    def _post_process(self, content, match_data):
        """
        Garantisce che l'articolo finisce correttamente e aggiunge conclusione standard se mancante.
        """
        if not content.endswith(('.', '!', '?')):
            sentences = content.split('.')
            if len(sentences) > 1:
                content = '.'.join(sentences[:-1]) + '.'
            conclusion = (
                f"\n\n<p>La partita tra {match_data.get('home_team')} e {match_data.get('away_team')} "
                f"si chiude con questo risultato che avrà sicuramente ripercussioni sulla classifica del fantacalcio. "
                "L'analisi dettagliata delle prestazioni individuali conferma l'importanza delle scelte tattiche in questa giornata di campionato.</p>"
            )
            content += conclusion
        return content

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
