def _build_detailed_players_info(self, match_data):
      print("DEBUG: Entrato in _build_detailed_players_info")
      """Costruisce descrizione usando i dati REALI del parser"""
        
      players_info = ""
      
      # ✅ USA I DATI REALI DAL PARSER
      home_players_names = match_data.get('home_players_names', [])
      away_players = match_data.get('away_players', [])
      home_bench_names = match_data.get('home_bench_names', [])
      away_bench = match_data.get('away_bench', [])
      print(f"🔍 DEBUG - Home: {len(home_players_names)} titolari + {len(home_bench_names)} panchina")
      print(f"🔍 DEBUG - Away: {len(away_players)} titolari + {len(away_bench)} panchina")
      # ✅ FORMAZIONE CASA CON NOMI REALI
      if home_players_names:
          players_info += f"\n**FORMAZIONE {match_data['home_team']} (TITOLARI):**\n"
          for player in home_players_names[:11]:  # Primi 11 titolari
              name = player.get('name', 'Sconosciuto')
              role = player.get('role', 'N/A')
              fanta_vote = player.get('fanta_vote', 0)
              vote = player.get('vote', 0)
              
              if fanta_vote:
                  players_info += f"- {name} ({role}): {fanta_vote:.1f} punti fantacalcio"
                  if vote and vote != fanta_vote:
                      players_info += f" (voto {vote:.1f})"
                  players_info += "\n"
          print(f"✅ Aggiunti {len(home_players_names)} giocatori casa titolari")
      # ✅ FORMAZIONE TRASFERTA CON NOMI REALI
      if away_players:
          players_info += f"\n**FORMAZIONE {match_data['away_team']} (TITOLARI):**\n"
          
          for player in away_players[:11]:  # Primi 11 titolari
              name = player.get('name', 'Sconosciuto')
              role = player.get('role', 'N/A')
              fanta_vote = player.get('fanta_vote', 0)
              vote = player.get('vote', 0)
              
              if fanta_vote:
                  players_info += f"- {name} ({role}): {fanta_vote:.1f} punti fantacalcio"
                  if vote and vote != fanta_vote:
                      players_info += f" (voto {vote:.1f})"
                  players_info += "\n"
          
          print(f"✅ Aggiunti {len(away_players)} giocatori trasferta titolari")
      
      # ✅ MIGLIORI PERFORMANCE DAL PARSER
      player_analysis = match_data.get('player_analysis', {})
      if player_analysis.get('top_performers'):
          players_info += f"\n**MIGLIORI PRESTAZIONI (DAL PARSER):**\n"
          for performer in player_analysis['top_performers'][:5]:
              players_info += f"- {performer}\n"
      
      # ✅ DEBUG: Mostra cosa stiamo inviando all'AI
      print(f"📋 FORMAZIONI COMPLETE COSTRUITE:")
      print("=" * 50)
      print(players_info[:600] + "..." if len(players_info) > 600 else players_info)
      print("=" * 50)
      
      return players_info
