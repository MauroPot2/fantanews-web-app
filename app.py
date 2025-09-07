import os
import uuid
import threading
import queue
import json
from dotenv import load_dotenv
from sqlalchemy import func, desc
from sqlalchemy.orm import joinedload
from datetime import datetime, timedelta
from flask import Flask, request, render_template, redirect, url_for, jsonify, Response
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from flask_migrate import Migrate

load_dotenv()
from extensions import db  # Importa l'istanza db da extensions.py
from models import Match, Article, Team, PlayerStat, Player
from utils.excel_parser import ExcelParser
from utils.perplexity_client import PerplexityClient

# ===== INIZIALIZZAZIONE APP =====
app = Flask(__name__)

# ✅ Configurazione da .env (come da tua specifica)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///fantacalcio.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.getenv('UPLOAD_FOLDER', 'static/uploads')
app.config['MATCHES_PER_PAGE'] = int(os.getenv('MATCHES_PER_PAGE', 10))
app.config['ARTICLES_PER_PAGE'] = int(os.getenv('ARTICLES_PER_PAGE', 6))
app.config['PERPLEXITY_API_KEY'] = os.getenv('PERPLEXITY_API_KEY')
app.config['PERPLEXITY_BASE_URL'] = os.getenv('PERPLEXITY_BASE_URL', 'https://api.perplexity.ai/chat/completions')

db.init_app(app)
migrate = Migrate(app, db)
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)



# ✅ Crea tabelle (come da tua specifica)
with app.app_context():
    db.create_all()

# ===== SISTEMA LOG STREAMING =====
admin_log_queue = queue.Queue()
active_admin_clients = set()

class AdminLogger:
    """Logger personalizzato per l'admin page con streaming SSE"""
    
    @staticmethod
    def log(level, message, extra=None):
        """Aggiunge un messaggio al log stream"""
        log_entry = {
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'level': level.upper(),
            'message': str(message),
            'extra': extra or {}
        }
        
        # Aggiunge alla coda per tutti i client connessi
        try:
            for _ in range(len(active_admin_clients)):
                admin_log_queue.put_nowait(log_entry)
        except queue.Full:
            pass
        
        # Log anche nella console
        print(f"[{log_entry['timestamp']}] {log_entry['level']}: {log_entry['message']}")

# Instance globale del logger
admin_logger = AdminLogger()

# ===== UTILITY FUNCTIONS =====
def allowed_file(filename):
    """Controlla se il file è un Excel valido"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ['xls', 'xlsx']

# ===== ROUTES PRINCIPALI =====

@app.route('/')
def index():
    """Homepage con statistiche"""
    try:
        total_matches = Match.query.count()
        total_articles = Article.query.count()
        latest_gameweek = db.session.query(db.func.max(Match.gameweek)).scalar()
        
        return render_template('index.html',
                             total_matches=total_matches,
                             total_articles=total_articles,
                             latest_gameweek=latest_gameweek)
    except Exception as e:
        print(f"Errore homepage: {e}")
        return render_template('index.html',
                             total_matches=0,
                             total_articles=0,
                             latest_gameweek=None)

@app.route('/matches')
def matches():
    """Lista partite con paginazione e filtri"""
    page = request.args.get('page', 1, type=int)
    gameweek = request.args.get('gameweek', type=int)
    
    query = Match.query
    if gameweek:
        query = query.filter_by(gameweek=gameweek)
    
    pagination = query.order_by(Match.gameweek.desc(), Match.id.desc()).paginate(
        page=page, 
        per_page=app.config['MATCHES_PER_PAGE'], 
        error_out=False
    )
    
    return render_template('matches.html', 
                         matches=pagination.items, 
                         pagination=pagination,
                         selected_gameweek=gameweek)

@app.route('/matches/<int:match_id>')
def match_detail(match_id):
    """Dettaglio singola partita"""
    match = Match.query.get_or_404(match_id)
    article = Article.query.filter_by(match_id=match_id).first()
    
    return render_template('match_detail.html', match=match, article=article)

@app.route('/articles')
def articles():
    """Lista articoli con paginazione"""
    page = request.args.get('page', 1, type=int)
    
    pagination = Article.query.order_by(Article.created_at.desc()).paginate(
        page=page, 
        per_page=app.config['ARTICLES_PER_PAGE'], 
        error_out=False
    )
    
    return render_template('articles.html', 
                         articles=pagination.items, 
                         pagination=pagination)

@app.route('/articles/<int:article_id>')
def article_detail(article_id):
    """Dettaglio singolo articolo"""
    article = Article.query.get_or_404(article_id)
    match = None
    if article.match_id:
        match = Match.query.get(article.match_id)
    
    # Altri articoli per sidebar
    articles_list = Article.query.order_by(Article.created_at.desc()).limit(10).all()
    
    return render_template('article_detail.html',
                         article=article,
                         match=match,
                         articles_list=articles_list)

@app.route('/teams')
def teams():
    teams_with_players = Team.query.options(joinedload(Team.players)).order_by(Team.name).all()
    return render_template('teams.html', teams=teams_with_players)

@app.route('/teams/<int:team_id>')
def team_detail(team_id):
    """Pagina dettaglio di una squadra"""
    try:
        # Recupera la squadra dal database
        team = Team.query.get_or_404(team_id)
        
        # Trova tutte le partite della squadra
        home_matches = Match.query.filter_by(home_team=team.name).all()
        away_matches = Match.query.filter_by(away_team=team.name).all()
        
        return render_template('team_detail.html', 
                             team=team,
                             home_matches=home_matches,
                             away_matches=away_matches)
    except Exception as e:
        print(f"Errore team detail: {e}")
        return redirect(url_for('index'))

@app.route('/standings')
def standings():
    """Classifica del campionato"""
    try:
        from utils.calculate_standings import calculate_standings
        standings_data = calculate_standings()
        return render_template('standings.html', standings=standings_data)
    except Exception as e:
        print(f"Errore classifica: {e}")
        return render_template('standings.html', standings=[])
    
@app.route('/stats')
def stats():
    """
    Gestisce la pagina delle statistiche.
    Recupera i dati necessari dal database e li passa al template.
    """
    try:
        # Recupera un dizionario di tutti i nomi delle squadre per un accesso efficiente
        teams_dict = {team.id: team.name for team in Team.query.all()}
        
        # Statistiche generali
        total_matches = Match.query.count()
        total_teams = Team.query.count()
        all_matches = Match.query.all()
        
        # Calcola la somma totale dei gol effettivi e dei punti
        total_goals_sum = sum(match.home_goals + match.away_goals for match in all_matches)
        total_points_sum = sum(match.home_score + match.away_score for match in all_matches)

        # Calcola le medie
        avg_goals_per_match = (total_goals_sum / total_matches) if total_matches > 0 else 0
        avg_points_per_match = (total_points_sum / total_matches) if total_matches > 0 else 0
        
        gameweek_stats_raw = db.session.query(
            Match.gameweek,
            func.count(Match.gameweek),
            func.sum(Match.home_score + Match.away_score),
            func.avg(Match.home_score + Match.away_score)
        ).group_by(Match.gameweek).order_by(Match.gameweek).all()

        gameweek_stats = {
            gw: {
                'matches': count,
                'total_goals': total_goals,
                'avg_goals': avg_goals
            } for gw, count, total_goals, avg_goals in gameweek_stats_raw
        }

        # Dati squadre
        teams = Team.query.order_by(Team.points.desc()).all()
        top_team = teams[0] if teams else None
        
        top_scorer_team = Team.query.order_by(Team.goals_for.desc()).first()
        
        best_defense = Team.query.filter(Team.matches_played > 0).order_by(Team.goals_against).first()

        # Partite più spettacolari (con più gol)
        high_scoring_matches = Match.query.order_by(
            (Match.home_score + Match.away_score).desc()
        ).limit(5).all()
        
        # Converte gli oggetti Match in dizionari per il template
        spectacular_matches = [
            {
                'home_team': match.home_team, 
                'away_team': match.away_team, 
                'home_score': match.home_score,
                'away_score': match.away_score,
                'gameweek': match.gameweek,
                'id': match.id
            } for match in high_scoring_matches
        ]
        
        # Statistiche individuali
        top_scorers = Player.query.order_by(Player.goals.desc()).limit(10).all()
        top_assisters = Player.query.order_by(Player.assists.desc()).limit(10).all()
        best_goalkeepers = Player.query.filter_by(is_goalkeeper=True).order_by(Player.clean_sheets.desc()).limit(5).all()
        
        # Nuove query per i top e flop fantavoto
        top_fantavoto_players = PlayerStat.query.options(joinedload(PlayerStat.player).joinedload(Player.team)).order_by(desc(PlayerStat.fantavoto)).limit(5).all()
        flop_fantavoto_players = PlayerStat.query.options(joinedload(PlayerStat.player).joinedload(Player.team)).order_by(PlayerStat.fantavoto.asc()).limit(5).all()

        return render_template(
            'stats.html',
            total_matches=total_matches,
            total_teams=total_teams,
            avg_goals_per_match=avg_goals_per_match,
            avg_points_per_match=avg_points_per_match,
            gameweek_stats=gameweek_stats,
            teams=teams,
            top_team=top_team,
            top_scorer_team=top_scorer_team,
            best_defense=best_defense,
            high_scoring_matches=spectacular_matches,
            top_scorers=top_scorers,
            top_assisters=top_assisters,
            best_goalkeepers=best_goalkeepers,
            top_fantavoto_players=top_fantavoto_players,
            flop_fantavoto_players=flop_fantavoto_players
        )

    except Exception as e:
        # Gestione degli errori
        print(f"Errore nella route stats: {e}")
        return render_template('errors/500.html'), 500

@app.route('/api/top-scorers')
def api_top_scorers():
    """Restituisce i migliori marcatori in formato JSON."""
    top_players = db.session.query(Player, func.sum(PlayerStat.goals).label('total_goals')) \
        .join(PlayerStat) \
        .group_by(Player.id) \
        .order_by(desc('total_goals')) \
        .limit(10).all()
        
    results = []
    for player, total_goals in top_players:
        results.append({
            'name': player.name,
            'goals': total_goals,
            'player_id': player.id,
            'team': player.team.name if player.team else 'Sconosciuto'
        })
    return jsonify(results)

@app.route('/api/top-assists')
def api_top_assists():
    """Restituisce i migliori assistman in formato JSON."""
    top_players = db.session.query(Player, func.sum(PlayerStat.assists).label('total_assists')) \
        .join(PlayerStat) \
        .group_by(Player.id) \
        .order_by(desc('total_assists')) \
        .limit(10).all()
        
    results = []
    for player, total_assists in top_players:
        results.append({
            'name': player.name,
            'assists': total_assists,
            'player_id': player.id,
            'team': player.team.name if player.team else 'Sconosciuto'
        })
    return jsonify(results)

@app.route('/player/<int:player_id>')
def player_stats_page(player_id):
    """Renderizza la pagina delle statistiche del giocatore con i dati Jinja."""
    player = Player.query.options(joinedload(Player.team)).get_or_404(player_id)
    
    player_stats_list = PlayerStat.query.filter_by(player_id=player_id).order_by(PlayerStat.match_id.desc()).all()
    
    # Calcolo delle statistiche aggregate
    total_goals = sum(s.goals for s in player_stats_list if s.goals is not None)
    total_assists = sum(s.assists for s in player_stats_list if s.assists is not None)
    
    fanta_votes = [s.fanta_vote for s in player_stats_list if s.fanta_vote is not None]
    average_fanta_vote = sum(fanta_votes) / len(fanta_votes) if fanta_votes else 0

    return render_template('player_stats.html', 
                           player=player, 
                           player_stats=player_stats_list,
                           total_goals=total_goals,
                           total_assists=total_assists,
                           average_fanta_vote=average_fanta_vote)

# ===== ADMIN ROUTES =====
@app.route('/admin')
def admin():
    """Pannello amministrazione"""
    try:
        total_matches = Match.query.count()
        total_articles = Article.query.count()
        total_teams = db.session.query(db.func.count(db.func.distinct(Match.home_team))).scalar() or 0
        latest_gameweek = db.session.query(db.func.max(Match.gameweek)).scalar()
        
        # Suggerisci prossima giornata
        suggested_gameweek = (latest_gameweek + 1) if latest_gameweek else 1
        
        return render_template('admin.html',
                             total_matches=total_matches,
                             total_articles=total_articles,
                             total_teams=total_teams,
                             latest_gameweek=latest_gameweek,
                             suggested_gameweek=suggested_gameweek)
    except Exception as e:
        print(f"Errore admin: {e}")
        return render_template('admin.html',
                             total_matches=0,
                             total_articles=0,
                             total_teams=0,
                             latest_gameweek=None,
                             suggested_gameweek=1)

@app.route('/admin/logs/stream')
def admin_log_stream():
    """SSE endpoint per streaming dei log admin"""
    def generate():
        # Registra questo client
        client_id = threading.current_thread().ident
        active_admin_clients.add(client_id)
        
        try:
            while True:
                try:
                    # Aspetta un nuovo log (timeout 30 secondi per heartbeat)
                    log_entry = admin_log_queue.get(timeout=30)
                    
                    # Format SSE
                    data = json.dumps(log_entry)
                    yield f"data: {data}\n\n"
                    
                except queue.Empty:
                    # Heartbeat per mantenere connessione viva
                    yield "data: {\"type\":\"heartbeat\"}\n\n"
                    
        except GeneratorExit:
            # Client disconnesso
            active_admin_clients.discard(client_id)
            print(f"Admin client {client_id} disconnesso")
    
    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Access-Control-Allow-Origin': '*'
        }
    )

@app.route('/admin/process', methods=['POST'])
def admin_process():
    """Processa Excel con log streaming"""
    try:
        admin_logger.log('info', '🚀 Iniziando processo elaborazione tabellino')
        
        # Validazioni
        if 'file' not in request.files:
            admin_logger.log('error', '❌ Nessun file caricato')
            return jsonify({'success': False, 'message': 'Nessun file caricato'})
        
        file = request.files['file']
        if file.filename == '':
            admin_logger.log('error', '❌ Nessun file selezionato')
            return jsonify({'success': False, 'message': 'Nessun file selezionato'})
        
        if not allowed_file(file.filename):
            admin_logger.log('error', '❌ Formato file non supportato. Usa Excel (.xlsx/.xls)')
            return jsonify({'success': False, 'message': 'Formato file non supportato'})
        
        # Parametri
        gameweek = request.form.get('gameweek', 1)
        generate_articles = 'generate_articles' in request.form
        update_standings = 'update_standings' in request.form
        overwrite_duplicates = 'overwrite_duplicates' in request.form
        
        admin_logger.log('info', f'📋 Parametri: Giornata {gameweek}, Articoli: {generate_articles}')
        
        # Salva file
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        admin_logger.log('success', f'📤 File salvato: {filename}')
        
        # Avvia processo in background
        admin_logger.log('info', '⚙️ Avviando elaborazione in background...')
        
        thread = threading.Thread(
            target=process_matches_with_logging,
            args=(filepath, gameweek, generate_articles, update_standings, overwrite_duplicates)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'message': 'Elaborazione avviata - segui i log qui sotto'
        })
        
    except Exception as e:
        admin_logger.log('error', f'💥 Errore server: {str(e)}')
        return jsonify({'success': False, 'message': f'Errore server: {str(e)}'})

@app.route('/admin/clear-database', methods=['POST'])
def clear_database():
    """Svuota il database (solo per admin)"""
    try:
        admin_logger.log('warning', '🗑️ Iniziando pulizia database...')
        
        # Rimuovi tutti i record
        Article.query.delete()
        Match.query.delete()
        Team.query.delete()
        db.session.commit()
        
        admin_logger.log('success', '✅ Database svuotato completamente')
        
        return jsonify({'success': True, 'message': 'Database svuotato con successo'})
        
    except Exception as e:
        admin_logger.log('error', f'❌ Errore pulizia database: {str(e)}')
        return jsonify({'success': False, 'message': f'Errore: {str(e)}'})

@app.route('/submit_match', methods=['POST'])
def submit_match():
    """
    Gestisce l'invio e l'elaborazione dei dati di una partita.
    """
    data = request.json
    try:
        # Recupera le squadre
        home_team = Team.query.filter_by(name=data['home_team_name']).first()
        away_team = Team.query.filter_by(name=data['away_team_name']).first()
        if not home_team or not away_team:
            return jsonify({'success': False, 'message': 'Squadra non trovata'}), 404

        # Aggiunge una nuova partita
        new_match = Match(
            home_team=home_team.name,
            away_team=away_team.name,
            home_score=data['home_score'],
            away_score=data['away_score'],
            gameweek=data['gameweek'],
            date_played=datetime.utcnow()
        )
        db.session.add(new_match)
        db.session.flush()  # Ottiene l'ID del match prima del commit

        # Aggiorna le statistiche di squadra
        home_team.matches_played += 1
        away_team.matches_played += 1
        home_team.points_for += data['home_score']
        away_team.points_for += data['away_score']
        home_team.points_against += data['away_score']
        away_team.points_against += data['home_score']

        home_goals = new_match.home_goals
        away_goals = new_match.away_goals
        home_team.goals_for += home_goals
        home_team.goals_against += away_goals
        away_team.goals_for += away_goals
        away_team.goals_against += home_goals

        if home_goals > away_goals:
            home_team.wins += 1
            away_team.losses += 1
        elif away_goals > home_goals:
            away_team.wins += 1
            home_team.losses += 1
        else:
            home_team.draws += 1
            away_team.draws += 1

        # Aggiorna le statistiche individuali dei giocatori
        for player_data in data.get('players', []):
            player = Player.query.filter_by(name=player_data['name']).first()
            if player:
                new_stat = PlayerStat(
                    player_id=player.id,
                    match_id=new_match.id,
                    fantavoto=player_data['fantavoto']
                )
                db.session.add(new_stat)
                
                # Aggiorna i gol/assist/clean sheets
                if 'goals' in player_data:
                    player.goals += player_data['goals']
                if 'assists' in player_data:
                    player.assists += player_data['assists']
                if player.is_goalkeeper and player_data.get('clean_sheet', False):
                    player.clean_sheets += 1
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Partita elaborata con successo!'}), 200

    except Exception as e:
        db.session.rollback()
        print(f"Errore nell'elaborazione del tabellino: {e}")
        return jsonify({'success': False, 'message': f"Errore: {str(e)}"}), 500
# ===== PROCESSO BACKGROUND =====
def get_or_create_team_and_player(db_session, team_name, player_name):
    """
    Trova o crea un team e un giocatore.
    """
    team = Team.query.filter_by(name=team_name).first()
    if not team:
        team = Team(name=team_name)
        db_session.add(team)
        db_session.flush() # Per ottenere l'ID prima del commit
        admin_logger.log('info', f'➕ Creato nuovo team: {team_name}')
    
    player = Player.query.filter_by(name=player_name, team_id=team.id).first()
    if not player:
        is_goalkeeper = 'P' in player_name.upper()
        player = Player(name=player_name, team_id=team.id, is_goalkeeper=is_goalkeeper)
        db_session.add(player)
        db_session.flush() # Per ottenere l'ID prima del commit
        admin_logger.log('info', f'➕ Creato nuovo giocatore: {player_name} ({team_name})')
        
    return team, player

def process_player_stats(db_session, saved_matches_data):
    """
    Elabora e salva le statistiche individuali dei giocatori.
    """
    admin_logger.log('info', '📊 Iniziando salvataggio statistiche giocatori...')
    
    for match, match_data in saved_matches_data:
        # Processa giocatori della squadra di casa
        for player_data in match_data.get('home_players', []) + match_data.get('home_bench', []):
            team, player = get_or_create_team_and_player(db_session, match_data['home_team'], player_data['name'])
            
            # Calcolo clean sheet per i portieri
            is_clean_sheet = False
            if player.is_goalkeeper:
                if match_data['away_score'] == 0:
                    is_clean_sheet = True
            
            # Sostituisci esplicitamente i valori None con 0.0
            player_vote = player_data.get('vote')
            player_fanta_vote = player_data.get('fanta_vote')
            
            player_stat = PlayerStat(
                match_id=match.id,
                player_id=player.id,
                is_starter=player_data in match_data.get('home_players', []),
                vote=player_vote if player_vote is not None else 0.0,
                fanta_vote=player_fanta_vote if player_fanta_vote is not None else 0.0,
                goals=player_data.get('stats', {}).get('goals', 0),
                assists=player_data.get('stats', {}).get('assists', 0),
                clean_sheet=is_clean_sheet
            )
            db_session.add(player_stat)
            
        # Processa giocatori della squadra in trasferta
        for player_data in match_data.get('away_players', []) + match_data.get('away_bench', []):
            team, player = get_or_create_team_and_player(db_session, match_data['away_team'], player_data['name'])
            
            # Calcolo clean sheet per i portieri
            is_clean_sheet = False
            if player.is_goalkeeper:
                if match_data['home_score'] == 0:
                    is_clean_sheet = True

            # Sostituisci esplicitamente i valori None con 0.0
            player_vote = player_data.get('vote')
            player_fanta_vote = player_data.get('fanta_vote')

            player_stat = PlayerStat(
                match_id=match.id,
                player_id=player.id,
                is_starter=player_data in match_data.get('away_players', []),
                vote=player_vote if player_vote is not None else 0.0,
                fanta_vote=player_fanta_vote if player_fanta_vote is not None else 0.0,
                goals=player_data.get('stats', {}).get('goals', 0),
                assists=player_data.get('stats', {}).get('assists', 0),
                clean_sheet=is_clean_sheet
            )
            db_session.add(player_stat)
    
    admin_logger.log('success', '📊 Statistiche giocatori salvate con successo.')

def process_matches_with_logging(filepath, gameweek, generate_articles=True, update_standings=True, overwrite_duplicates=False):
    """
    Processo background con log dettagliato
    Questa è la tua funzione originale, integrata e aggiornata.
    """
    try:
        with app.app_context():
            
            # ===== STEP 1: PARSING =====
            admin_logger.log('info', '🔍 Iniziando parsing del file Excel...')
            
            parser = ExcelParser(filepath)
            matches_data = parser.parse_matches()

            if not matches_data:
                admin_logger.log('error', '❌ Nessuna partita trovata nel file Excel')
                return
            
            admin_logger.log('success', f'✅ Trovate {len(matches_data)} partite nel file')
            
            # ===== STEP 2: PROCESSING =====
            admin_logger.log('info', '⚙️ Elaborando dati partite...')
            processed_matches = []
            
            for i, original_match in enumerate(matches_data):
                admin_logger.log('info', f'⚙️ Processing partita {i+1}: {original_match.get("home_team")} vs {original_match.get("away_team")}')
                
                processed_match = {
                    'id': original_match.get('id'), # Id partita se disponibile
                    'home_team': original_match.get('home_team', 'Sconosciuto'),
                    'away_team': original_match.get('away_team', 'Sconosciuto'),
                    'home_score': original_match.get('home_score', 0), # Gol reali o punteggio reale, coerente con DB
                    'away_score': original_match.get('away_score', 0),
                    'home_total': float(original_match.get('home_total', 0.0)), # Punteggio fantacalcio complessivo
                    'away_total': float(original_match.get('away_total', 0.0)),
                    'gameweek': int(gameweek),
                    'home_formation_code': original_match.get('home_formation_code', ''),
                    'away_formation_code': original_match.get('away_formation_code', ''),
                    'home_players': original_match.get('home_players', []), # Lista dizionari giocatori titolari casa
                    'away_players': original_match.get('away_players', []), # Lista dizionari giocatori titolari trasferta
                    'home_bench': original_match.get('home_bench', []), # Lista dizionari panchina casa
                    'away_bench': original_match.get('away_bench', []), # Lista dizionari panchina trasferta
                    'home_modifiers': original_match.get('home_modifiers', {}),# Modificatori casa (bonus/malus)
                    'away_modifiers': original_match.get('away_modifiers', {}),# Modificatori trasferta
                    'home_timestamp': original_match.get('home_timestamp', ''),
                    'away_timestamp': original_match.get('away_timestamp', ''),
                    'player_analysis': original_match.get('player_analysis', {}), # Dati analisi top/poor performers, bonus/malus, ecc.
                }

                processed_matches.append(processed_match)
            
            admin_logger.log('success', f'✅ Elaborate {len(processed_matches)} partite')
            
            # ===== STEP 3: SALVATAGGIO DATABASE =====
            admin_logger.log('info', '💾 Salvando partite nel database...')
            
            saved_matches = []
            duplicate_count = 0
            
            for match_data in processed_matches:
                admin_logger.log('info', f'💾 Salvando: {match_data["home_team"]} vs {match_data["away_team"]}')
                
                # Controllo duplicati
                existing = Match.query.filter_by(
                    home_team=match_data['home_team'],
                    away_team=match_data['away_team'],
                    gameweek=match_data['gameweek']
                ).first()
                
                if existing:
                    if overwrite_duplicates:
                        existing.home_score = match_data['home_total']
                        existing.away_score = match_data['away_total']
                        saved_matches.append((existing, match_data))
                        admin_logger.log('warning', f'🔄 Aggiornata partita esistente: {match_data["home_team"]} vs {match_data["away_team"]}')
                    else:
                        duplicate_count += 1
                        admin_logger.log('warning', f'⚠️ Saltata partita duplicata: {match_data["home_team"]} vs {match_data["away_team"]}')
                        continue
                else:
                    # Nuova partita
                    match = Match(
                        home_team=match_data['home_team'],
                        away_team=match_data['away_team'],
                        home_score=match_data['home_total'],
                        away_score=match_data['away_total'],
                        gameweek=match_data['gameweek']
                    )
                    
                    db.session.add(match)
                    db.session.flush()
                    saved_matches.append((match, match_data))
                    admin_logger.log('success', f'✅ Salvata nuova partita (ID: {match.id})')
            
            db.session.commit()
            admin_logger.log('success', f'💾 Database aggiornato: {len(saved_matches)} partite salvate, {duplicate_count} duplicate')
            
            # ===== STEP 4: SALVATAGGIO STATISTICHE GIOCATORI =====
            if saved_matches:
                try:
                    process_player_stats(db.session, saved_matches)
                    db.session.commit()
                except Exception as e:
                    db.session.rollback()
                    admin_logger.log('error', f'⚠️ Errore salvataggio statistiche giocatori: {str(e)}')
            
            # ===== STEP 5: ARTICOLI AI =====
            articles_generated = 0
            if generate_articles and saved_matches:
                admin_logger.log('info', '🤖 Iniziando generazione articoli AI...')
                
                try:
                    perplexity = PerplexityClient()

                    for i, (match, match_data) in enumerate(saved_matches):
                        try:
                            article_content = perplexity.generate_article(match_data)
                            article = Article(
                                match_id=match.id,
                                title=f"{match.home_team} vs {match.away_team}: Cronaca e Analisi",
                                content=article_content
                            )
                            db.session.add(article)
                            articles_generated += 1
                            admin_logger.log('success', f'✅ Articolo generato per {match.home_team} vs {match.away_team}')
                            
                        except Exception as e:
                            admin_logger.log('warning', f'⚠️ Errore generazione articolo per {match.home_team} vs {match.away_team}: {str(e)}')
                            
                            # Fallback article
                            fallback = Article(
                                match_id=match.id,
                                title=f"{match.home_team} vs {match.away_team}: Resoconto",
                                content=f"<p>Partita conclusa {match.home_score:.1f} - {match.away_score:.1f}.</p>"
                            )
                            db.session.add(fallback)
                            articles_generated += 1
                    
                    db.session.commit()
                    admin_logger.log('success', f'📰 Generazione articoli completata: {articles_generated} articoli creati')
                    
                except ImportError:
                    admin_logger.log('warning', '⚠️ PerplexityClient non disponibile - articoli saltati')
            else:
                admin_logger.log('info', '📰 Generazione articoli saltata')
            
            # ===== STEP 6: CLASSIFICA =====
            if update_standings:
                admin_logger.log('info', '📊 Aggiornando classifica...')
                
                try:
                    from utils.calculate_standings import calculate_standings
                    calculate_standings()
                    admin_logger.log('success', '📊 Classifica aggiornata con successo')
                except Exception as e:
                    admin_logger.log('error', f'⚠️ Errore aggiornamento classifica: {str(e)}')
            else:
                admin_logger.log('info', '📊 Aggiornamento classifica saltato')
            
            # ===== COMPLETAMENTO =====
            admin_logger.log('success', '🎉 ELABORAZIONE COMPLETATA CON SUCCESSO!')
            admin_logger.log('info', f'📝 Riepilogo: {len(saved_matches)} partite, {articles_generated} articoli, giornata {gameweek}')
            
    except Exception as e:
        admin_logger.log('error', f'💥 ERRORE GENERALE: {str(e)}')
        import traceback
        admin_logger.log('error', f'🔍 Stack trace: {traceback.format_exc()}')
    finally:
        if os.path.exists(filepath):
            os.remove(filepath)
            admin_logger.log('info', f'🗑️ File temporaneo {filepath} cancellato.')

# ===== ERROR HANDLERS =====
@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('errors/500.html'), 500

# ===== DEBUG ROUTES (solo in development) =====
if app.debug:
    @app.route('/debug/routes')
    def debug_routes():
        """Mostra tutte le route disponibili"""
        routes = []
        for rule in app.url_map.iter_rules():
            routes.append({
                'endpoint': rule.endpoint,
                'methods': list(rule.methods),
                'url': str(rule)
            })
        return jsonify(routes)

# ===== RUN APP =====
if __name__ == '__main__':
    debug_mode = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    port = int(os.getenv('FLASK_RUN_PORT', 5000))
    
    print("🚀 Avviando FantaNews...")
    print(f"📍 Debug mode: {debug_mode}")
    print(f"🌐 Port: {port}")
    
    app.run(debug=debug_mode, host='0.0.0.0', port=port, threaded=True)
