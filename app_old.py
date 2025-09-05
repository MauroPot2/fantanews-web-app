# app.py
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from dotenv import load_dotenv
from utils.calculate_standings import calculate_standings
import os
from datetime import datetime, timedelta
from threading import Thread
import threading
import uuid
from werkzeug.utils import secure_filename

# Carica variabili d'ambiente
load_dotenv()

from models import db, Season, Team, Match, Article

# Progress bar stato upload/elaborazione
processing_status_lock = threading.Lock()
processing_status = {}

def cleanup_expired_sessions():
    """Pulisce le sessioni scadute ogni 10 minuti"""
    while True:
        try:
            import time
            time.sleep(600)  # 10 minuti
            
            current_time = datetime.now()
            expired_sessions = []
            
            with processing_status_lock:
                for session_id, status in processing_status.items():
                    created_at = status.get('created_at', current_time)
                    if current_time - created_at > timedelta(minutes=30):
                        expired_sessions.append(session_id)
                
                for session_id in expired_sessions:
                    del processing_status[session_id]
                    print(f"🧹 Sessione scaduta rimossa: {session_id}")
                    
        except Exception as e:
            print(f"❌ Errore cleanup sessioni: {e}")

# Avvia cleanup thread
cleanup_thread = threading.Thread(target=cleanup_expired_sessions)
cleanup_thread.daemon = True
cleanup_thread.start()

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'xlsx', 'xls'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def create_app():
    app = Flask(__name__)

    # Configurazione da .env
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///fantacalcio.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = os.getenv('UPLOAD_FOLDER', 'static/uploads')
    app.config['MATCHES_PER_PAGE'] = int(os.getenv('MATCHES_PER_PAGE', 10))
    app.config['ARTICLES_PER_PAGE'] = int(os.getenv('ARTICLES_PER_PAGE', 6))
    app.config['PERPLEXITY_API_KEY'] = os.getenv('PERPLEXITY_API_KEY')
    app.config['PERPLEXITY_BASE_URL'] = os.getenv('PERPLEXITY_BASE_URL', 'https://api.perplexity.ai/chat/completions')

    # Inizializza database
    db.init_app(app)
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    with app.app_context():
        db.create_all()

    # ----- Funzione classifica -----
    def calculate_standings():
        from utils.fantacalcio_utils import points_to_goals

        if Match.query.count() == 0:
            return []

        teams = Team.query.all()
        for team in teams:
            team.points = 0
            team.matches_played = 0
            team.wins = 0
            team.draws = 0
            team.losses = 0
            team.goals_for = 0
            team.goals_against = 0
            if hasattr(team, 'points_for'):
                team.points_for = 0.0
            if hasattr(team, 'points_against'):
                team.points_against = 0.0

        matches = Match.query.all()
        for match in matches:
            home_team = Team.query.filter_by(name=match.home_team).first()
            if not home_team:
                home_team = Team(name=match.home_team,
                                 points=0, matches_played=0, wins=0, draws=0, losses=0,
                                 goals_for=0, goals_against=0, points_for=0.0, points_against=0.0)
                db.session.add(home_team)
                db.session.flush()
            away_team = Team.query.filter_by(name=match.away_team).first()
            if not away_team:
                away_team = Team(name=match.away_team,
                                 points=0, matches_played=0, wins=0, draws=0, losses=0,
                                 goals_for=0, goals_against=0, points_for=0.0, points_against=0.0)
                db.session.add(away_team)
                db.session.flush()

            home_goals = points_to_goals(match.home_score)
            away_goals = points_to_goals(match.away_score)

            home_team.matches_played += 1
            away_team.matches_played += 1
            home_team.goals_for += home_goals
            home_team.goals_against += away_goals
            away_team.goals_for += away_goals
            away_team.goals_against += home_goals
            home_team.points_for += match.home_score
            home_team.points_against += match.away_score
            away_team.points_for += match.away_score
            away_team.points_against += match.home_score

            if home_goals > away_goals:
                home_team.wins += 1
                home_team.points += 3
                away_team.losses += 1
            elif away_goals > home_goals:
                away_team.wins += 1
                away_team.points += 3
                home_team.losses += 1
            else:
                home_team.draws += 1
                away_team.draws += 1
                home_team.points += 1
                away_team.points += 1

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"Error updating standings: {e}")
            return []

        return Team.query.order_by(
            Team.points.desc(),
            (Team.goals_for - Team.goals_against).desc(),
            Team.goals_for.desc()
        ).all()

    # ---- ROUTES ----

# app.py - Aggiungi questa route
    # app.py - Route index corretta
    @app.route('/')
    def index():
        """Homepage con statistiche dal database"""
        try:
            # Recupera statistiche dal database
            total_matches = Match.query.count()
            total_articles = Article.query.count()
            latest_gameweek = db.session.query(db.func.max(Match.gameweek)).scalar()
            
            return render_template('index.html', 
                                total_matches=total_matches,
                                total_articles=total_articles,
                                latest_gameweek=latest_gameweek)
        except Exception as e:
            # Se il database non è ancora inizializzato, usa valori di default
            print(f"Errore nel recuperare dati per homepage: {e}")
            return render_template('index.html', 
                                total_matches=0,
                                total_articles=0,
                                latest_gameweek=None)


    @app.route('/home')
    def home():
        try:
            max_recent = int(os.getenv('MAX_RECENT_MATCHES', 5))
            recent_matches = Match.query.order_by(Match.date_played.desc()).limit(max_recent).all()
            standings = calculate_standings()[:5]
            return render_template('home.html', recent_matches=recent_matches, standings=standings)
        except Exception as e:
            print(f"Error in home route: {e}")
            return render_template('home.html', recent_matches=[], standings=[])

    @app.route('/standings')
    def standings():
        try:
            data = calculate_standings()
            return render_template('standings.html', standings=data)
        except Exception as e:
            print(f"Error in standings route: {e}")
            flash('Errore nel calcolo della classifica', 'error')
            return render_template('standings.html', standings=[])

    @app.route('/admin')
    def admin():
        """Pannello admin migliorato con statistiche"""
        try:
            # Statistiche dashboard
            total_matches = Match.query.count()
            total_articles = Article.query.count()
            total_teams = Team.query.count()
            latest_gameweek = db.session.query(db.func.max(Match.gameweek)).scalar()
            suggested_gameweek = (latest_gameweek + 1) if latest_gameweek else 1
            
            # Attività recente (se hai una tabella di log)
            recent_activity = []  # Implementa se necessario
            
            return render_template('admin.html',
                                total_matches=total_matches,
                                total_articles=total_articles,
                                total_teams=total_teams,
                                latest_gameweek=latest_gameweek,
                                suggested_gameweek=suggested_gameweek,
                                recent_activity=recent_activity)
        except Exception as e:
            print(f"Errore admin dashboard: {e}")
            return render_template('admin.html')

    @app.route('/admin/clear-database', methods=['POST'])
    def clear_database():
        """Svuota completamente il database"""
        try:
            Article.query.delete()
            Match.query.delete()
            Team.query.delete()
            db.session.commit()
            
            return jsonify({'success': True, 'message': 'Database svuotato'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)})

    @app.route('/admin/export-data')
    def export_data():
        """Esporta dati in CSV"""
        try:
            # Implementa export se necessario
            return jsonify({'message': 'Export non ancora implementato'})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    # app.py - Aggiungi questa route
    @app.route('/admin/process', methods=['POST'])
    def process_matches():
        """Processa il file Excel caricato"""
        if request.method == 'POST':
            try:
                # Controlla se c'è un file
                if 'file' not in request.files:
                    return jsonify({'success': False, 'message': 'Nessun file caricato'})
                
                file = request.files['file']
                if file.filename == '':
                    return jsonify({'success': False, 'message': 'Nessun file selezionato'})
                
                # Parametri del form
                gameweek = request.form.get('gameweek', 1)
                generate_articles = 'generate_articles' in request.form
                update_standings = 'update_standings' in request.form
                overwrite_duplicates = 'overwrite_duplicates' in request.form
                
                # Salva il file
                if file and file.filename.endswith(('.xlsx', '.xls')):
                    filename = secure_filename(file.filename)
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    filename = f"{timestamp}_{filename}"
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(filepath)
                    
                    # Genera session ID per tracking
                    session_id = str(uuid.uuid4())

                                # ✅ INIZIALIZZA SUBITO LO STATUS
                    with processing_status_lock:
                        processing_status[session_id] = {
                            'step': 0,
                            'status': 'starting',
                            'message': 'Processo inizializzato',
                            'percent': 0,
                            'completed': False,
                            'success': False,
                            'created_at': datetime.now()  # ✅ Timestamp creazione
                        }
                        print(f"📤 File salvato: {filepath}")
                        print(f"🆔 Session ID creato: {session_id}")
                        print(f"📊 Status inizializzato: {processing_status[session_id]}")
                
                # Avvia processo in background
                thread = threading.Thread(
                    target=process_matches_background,
                    args=(session_id, filepath, gameweek, generate_articles, update_standings, overwrite_duplicates)
                )
                thread.daemon = True
                thread.start()
                
                return jsonify({
                    'success': True, 
                    'session_id': session_id,
                    'message': 'Elaborazione avviata con successo'
                })
                
            except Exception as e:
                print(f"❌ Errore process_matches: {e}")
                return jsonify({'success': False, 'message': f'Errore server: {str(e)}'})

        @app.route('/admin/status/<session_id>')
        def get_status(session_id):
            """Ritorna lo status con gestione migliorata"""
            
            print(f"🔍 Richiesta status per sessione: {session_id}")
            
            with processing_status_lock:
                status = processing_status.get(session_id, None)
            
            if not status:
                print(f"❌ Sessione {session_id} non trovata in {list(processing_status.keys())}")
                return jsonify({
                    'step': 0,
                    'status': 'error',
                    'message': 'Sessione non trovata o scaduta',
                    'percent': 0,
                    'completed': True,
                    'success': False,
                    'error': 'Sessione non valida',
                    'should_stop_polling': True
                })
            
            # ✅ Verifica scadenza (30 minuti)
            created_at = status.get('created_at', datetime.now())
            if datetime.now() - created_at > timedelta(minutes=30):
                print(f"⏰ Sessione {session_id} scaduta")
                
                # Rimuovi sessione scaduta
                with processing_status_lock:
                    if session_id in processing_status:
                        del processing_status[session_id]
                
                return jsonify({
                    'step': 0,
                    'status': 'expired',
                    'message': 'Sessione scaduta',
                    'percent': 0,
                    'completed': True,
                    'success': False,
                    'error': 'Sessione scaduta per timeout',
                    'should_stop_polling': True
                })
            
            # Forza tipo booleano
            status['completed'] = bool(status.get('completed', False))
            status['should_stop_polling'] = status['completed']
            
            print(f"✅ Status trovato: step={status.get('step')}, completed={status['completed']}")
            
            return jsonify(status)


    # app.py - Route status migliorata con cleanup automatico
    @app.route('/admin/status/<session_id>')
    def get_status(session_id):
        """Ritorna lo status con cleanup automatico"""
        
        status = processing_status.get(session_id, None)
        
        if not status:
            # Sessione non trovata
            return jsonify({
                'step': 0,
                'status': 'error',
                'message': 'Sessione non trovata o scaduta',
                'percent': 0,
                'completed': True,
                'success': False,
                'error': 'Sessione non valida',
                'should_stop_polling': True  # ✅ Flag esplicito per fermare polling
            })
        
        # Forza tipo booleano
        status['completed'] = bool(status.get('completed', False))
        status['should_stop_polling'] = status['completed']  # ✅ Flag chiaro
        
        # ✅ AUTO-CLEANUP: Rimuovi sessioni completate dopo 30 secondi
        if status['completed']:
            def delayed_cleanup():
                import time
                time.sleep(30)
                if session_id in processing_status:
                    del processing_status[session_id]
                    print(f"🧹 Sessione {session_id} rimossa automaticamente")
            
            import threading
            cleanup_thread = threading.Thread(target=delayed_cleanup)
            cleanup_thread.daemon = True
            cleanup_thread.start()
        
        return jsonify(status)


    @app.route('/matches')
    def matches():
        matches = Match.query.all()
        
        # ✅ Verifica che i dati siano numerici
        for match in matches:
            try:
                match.home_score = float(match.home_score)
                match.away_score = float(match.away_score)
            except (ValueError, TypeError):
                match.home_score = 0.0
                match.away_score = 0.0
        
        return render_template('matches.html', matches=matches)


    # app.py - Aggiungi questa route
    @app.route('/articles')
    def articles():
        """Mostra tutti gli articoli"""
        articles = Article.query.order_by(Article.created_at.desc()).all()
        return render_template('articles.html', articles=articles)

    @app.route('/articles/<int:article_id>')
    def article_detail(article_id):
        """Mostra dettaglio articolo"""
        article = Article.query.get_or_404(article_id)
        match = Match.query.get(article.match_id)
        return render_template('article_detail.html', article=article, match=match)

    @app.route('/matches/<int:match_id>')
    def match_detail(match_id):
        """Mostra i dettagli di una partita con articolo associato"""
        
        # Recupera la partita
        match = Match.query.get_or_404(match_id)
        
        # ✅ FIX: Recupera l'articolo associato
        article = Article.query.filter_by(match_id=match_id).first()
        
        # Debug per verificare
        if article:
            print(f"✅ Articolo trovato per match {match_id}: {article.title}")
        else:
            print(f"⚠️ Nessun articolo trovato per match {match_id}")
        
        return render_template('match_detail.html', match=match, article=article)

    @app.route('/teams')
    def teams():
        try:
            teams = Team.query.order_by(Team.name).all()
            return render_template('teams.html', teams=teams)
        except Exception as e:
            print(f"Error in teams route: {e}")
            return render_template('teams.html', teams=[])

    @app.route('/team/<team_name>')
    def team_detail(team_name):
        try:
            team = Team.query.filter_by(name=team_name).first_or_404()
            home_matches = Match.query.filter_by(home_team=team_name).all()
            away_matches = Match.query.filter_by(away_team=team_name).all()
            return render_template('team_detail.html', team=team, home_matches=home_matches, away_matches=away_matches)
        except Exception as e:
            print(f"Error in team detail: {e}")
            flash('Squadra non trovata', 'error')
            return redirect(url_for('teams'))

    @app.route('/stats')
    def stats():
        try:
            total_matches = Match.query.count()
            total_teams = Team.query.count()
            top_team = Team.query.order_by(Team.points.desc()).first()
            top_scorer_team = Team.query.order_by(Team.goals_for.desc()).first()
            avg_goals_per_match = 0
            if total_matches > 0:
                all_matches = Match.query.all()
                total_goals = sum(match.home_score + match.away_score for match in all_matches)
                avg_goals_per_match = total_goals / total_matches
            high_scoring_matches = Match.query.order_by((Match.home_score + Match.away_score).desc()).limit(5).all()
            return render_template('stats.html', total_matches=total_matches, total_teams=total_teams,
                                   top_team=top_team, top_scorer_team=top_scorer_team,
                                   avg_goals_per_match=avg_goals_per_match,
                                   high_scoring_matches=high_scoring_matches)
        except Exception as e:
            print(f"Error in stats route: {e}")
            return render_template('stats.html', total_matches=0, total_teams=0,
                                   top_team=None, top_scorer_team=None, avg_goals_per_match=0,
                                   high_scoring_matches=[])

    @app.errorhandler(404)
    def not_found(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('errors/500.html'), 500

    return app

# app.py - Nuova versione di process_matches_background
# app.py - Funzione process_matches_background aggiornata
# app.py - Funzione process_matches_background completa e corretta

def process_matches_background(session_id, filepath, gameweek, generate_articles=True, update_standings=True, overwrite_duplicates=False):
    """Processo in background per elaborare partite con gestione status robusta"""
    
    def update_status(step, status, message, percent, **kwargs):
        """Aggiorna lo status del processo in modo thread-safe"""
        with processing_status_lock:
            if session_id in processing_status:
                processing_status[session_id].update({
                    'step': step,
                    'status': status,
                    'message': message,
                    'percent': percent,
                    'updated_at': datetime.now(),
                    **kwargs
                })
                print(f"📊 [{session_id}] Step {step}: {message} ({percent}%)")
            else:
                print(f"⚠️ Sessione {session_id} non trovata per aggiornamento status")
    
    try:
        with app.app_context():
            
            print(f"🚀 Processo background avviato per sessione: {session_id}")
            
            # ✅ Verifica che la sessione esista ancora
            with processing_status_lock:
                if session_id not in processing_status:
                    print(f"❌ Sessione {session_id} persa durante l'avvio")
                    return
            
            # ===== STEP 1: PARSING =====
            update_status(1, 'processing', 'Parsing tabellino Excel...', 10)
            
            from utils.excel_parser import ExcelParser
            parser = ExcelParser(filepath)
            matches_data = parser.parse_matches()
            
            if not matches_data:
                update_status(0, 'error', 'Nessuna partita trovata nel tabellino', 0, 
                             completed=True, success=False, error='File Excel vuoto o non valido')
                return
            
            print(f"✅ Trovati {len(matches_data)} match dal parser")
            
            # ✅ Crea processed_matches con gameweek garantito
            processed_matches = []
            for i, original_match in enumerate(matches_data):
                print(f"🔧 Processing match {i}: {original_match.get('home_team')} vs {original_match.get('away_team')}")
                
                processed_match = {
                    'home_team': original_match['home_team'],
                    'away_team': original_match['away_team'],
                    'home_total': original_match['home_total'],
                    'away_total': original_match['away_total'],
                    'gameweek': int(gameweek),
                    'home_score': original_match.get('home_score', 0),
                    'away_score': original_match.get('away_score', 0),
                    'home_formation_code': original_match.get('home_formation_code', ''),
                    'away_formation_code': original_match.get('away_formation_code', ''),
                    'home_players': original_match.get('home_players', []),
                    'away_players': original_match.get('away_players', []),
                    'player_analysis': original_match.get('player_analysis', {})  # Per AI
                }
                
                processed_matches.append(processed_match)
                print(f"✅ Match {i} processato con gameweek: {processed_match['gameweek']}")
            
            update_status(2, 'completed', f'Trovate {len(processed_matches)} partite', 25)
            
            # ===== STEP 2: SALVATAGGIO =====
            update_status(3, 'processing', 'Salvataggio partite nel database...', 40)
            
            saved_matches = []
            duplicate_count = 0
            
            for match_data in processed_matches:
                print(f"💾 Salvando: {match_data['home_team']} vs {match_data['away_team']} (Giornata {match_data['gameweek']})")
                
                # Controlla duplicati
                existing = Match.query.filter_by(
                    home_team=match_data['home_team'],
                    away_team=match_data['away_team'],
                    gameweek=match_data['gameweek']
                ).first()
                
                if existing:
                    if overwrite_duplicates:
                        # Sovrascrivi
                        existing.home_score = match_data['home_total']
                        existing.away_score = match_data['away_total']
                        saved_matches.append((existing, match_data))
                        print(f"🔄 Aggiornato: {match_data['home_team']} vs {match_data['away_team']}")
                    else:
                        duplicate_count += 1
                        print(f"⚠️ Duplicate saltato: {match_data['home_team']} vs {match_data['away_team']}")
                        continue
                else:
                    # Nuovo match
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
                    print(f"✅ Salvato: Match ID {match.id}")
            
            db.session.commit()
            
            message = f'Salvate {len(saved_matches)} partite'
            if duplicate_count > 0:
                message += f' ({duplicate_count} duplicate)'
            
            update_status(3, 'completed', message, 60)
            
            # ===== STEP 3: ARTICOLI (se richiesto) =====
            articles_generated = 0
            if generate_articles and saved_matches:
                update_status(4, 'processing', 'Generazione articoli AI...', 75)
                
                try:
                    from utils.perplexity_client import PerplexityClient
                    perplexity = PerplexityClient()
                    
                    for i, (match, data) in enumerate(saved_matches):
                        try:
                            progress = 75 + int((i / len(saved_matches)) * 15)
                            update_status(4, 'processing', f'Articolo {i+1}/{len(saved_matches)}', progress)
                            
                            print(f"🤖 Generando articolo per: {match.home_team} vs {match.away_team}")
                            
                            article_content = perplexity.generate_article(data)
                            
                            article = Article(
                                match_id=match.id,
                                title=f"{match.home_team} vs {match.away_team}: Cronaca e Analisi",
                                content=article_content
                            )
                            
                            db.session.add(article)
                            articles_generated += 1
                            
                        except Exception as e:
                            print(f"❌ Errore articolo per match {match.id}: {e}")
                            
                            # Fallback articolo
                            fallback = Article(
                                match_id=match.id,
                                title=f"{match.home_team} vs {match.away_team}: Resoconto",
                                content=f"<p>Partita conclusa {match.home_score:.1f} - {match.away_score:.1f}.</p>"
                            )
                            db.session.add(fallback)
                            articles_generated += 1
                    
                    db.session.commit()
                    update_status(4, 'completed', f'Generati {articles_generated} articoli', 90)
                    
                except ImportError:
                    print("⚠️ PerplexityClient non disponibile")
                    update_status(4, 'completed', 'Articoli saltati (Perplexity non disponibile)', 90)
            else:
                update_status(4, 'completed', 'Generazione articoli saltata', 90)
            
            # ===== STEP 4: CLASSIFICA (se richiesto) =====
            if update_standings:
                update_status(5, 'processing', 'Aggiornamento classifica...', 95)
                
                try:
                    from utils.calculate_standings import calculate_standings
                    calculate_standings()
                    update_status(5, 'completed', 'Classifica aggiornata', 98)
                except Exception as e:
                    print(f"⚠️ Errore classifica: {e}")
                    update_status(5, 'error', f'Errore classifica: {e}', 98)
            else:
                update_status(5, 'completed', 'Aggiornamento classifica saltato', 98)
            
            # ===== COMPLETAMENTO =====
            update_status(5, 'completed', 'Elaborazione completata!', 100, 
                         completed=True, 
                         success=True, 
                         gameweek=int(gameweek),
                         matches_processed=len(saved_matches),
                         articles_generated=articles_generated)
            
            print(f"🎉 PROCESSO COMPLETATO:")
            print(f"  📝 Partite elaborate: {len(saved_matches)}")
            print(f"  📰 Articoli generati: {articles_generated}")
            print(f"  🔄 Duplicate saltate: {duplicate_count}")
            
    except Exception as e:
        print(f"💥 ERRORE GENERALE nel background: {e}")
        
        import traceback
        traceback.print_exc()
        
        update_status(0, 'error', f'Errore: {str(e)}', 0, 
                     completed=True, success=False, error=str(e))
    def update_status(step, status, message, percent, **kwargs):
        processing_status[session_id] = {
            'step': step, 'status': status, 'message': message, 'percent': percent, **kwargs
        }
    
    try:
        with app.app_context():
            
            # ===== STEP 1: PARSING =====
            update_status(1, 'processing', 'Parsing tabellino Excel...', 10)
            
            from utils.excel_parser import ExcelParser
            parser = ExcelParser(filepath)
            matches_data = parser.parse_matches()
            
            if not matches_data:
                raise ValueError("Nessuna partita trovata nel tabellino")
            
            print(f"🔍 DEBUG: Trovati {len(matches_data)} match dal parser")
            
            # Crea processed_matches con gameweek garantito
            processed_matches = []
            for i, original_match in enumerate(matches_data):
                print(f"🔧 Processing match {i}: {original_match.get('home_team')} vs {original_match.get('away_team')}")
                
                processed_match = {
                    'home_team': original_match['home_team'],
                    'away_team': original_match['away_team'],
                    'home_total': original_match['home_total'],
                    'away_total': original_match['away_total'],
                    'gameweek': int(gameweek),
                    'home_score': original_match.get('home_score', 0),
                    'away_score': original_match.get('away_score', 0),
                    'home_formation_code': original_match.get('home_formation_code', ''),
                    'away_formation_code': original_match.get('away_formation_code', ''),
                    'home_players': original_match.get('home_players', []),
                    'away_players': original_match.get('away_players', [])
                }
                
                processed_matches.append(processed_match)
                print(f"✅ Match {i} processato con gameweek: {processed_match['gameweek']}")
            
            update_status(2, 'completed', f'Trovate {len(processed_matches)} partite', 25)
            
            # ===== STEP 2: SALVATAGGIO =====
            update_status(3, 'processing', 'Salvataggio partite nel database...', 40)
            
            saved_matches = []
            duplicate_count = 0
            
            for match_data in processed_matches:
                print(f"💾 Salvando: {match_data['home_team']} vs {match_data['away_team']} (Giornata {match_data['gameweek']})")
                
                # Controlla duplicati
                existing = Match.query.filter_by(
                    home_team=match_data['home_team'],
                    away_team=match_data['away_team'],
                    gameweek=match_data['gameweek']
                ).first()
                
                if existing:
                    if overwrite_duplicates:
                        # Sovrascrivi
                        existing.home_score = match_data['home_total']
                        existing.away_score = match_data['away_total']
                        saved_matches.append((existing, match_data))
                        print(f"🔄 Aggiornato: {match_data['home_team']} vs {match_data['away_team']}")
                    else:
                        duplicate_count += 1
                        print(f"⚠️ Duplicate saltato: {match_data['home_team']} vs {match_data['away_team']}")
                        continue
                else:
                    # Nuovo match
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
                    print(f"✅ Salvato: Match ID {match.id}")
            
            db.session.commit()
            
            message = f'Salvate {len(saved_matches)} partite'
            if duplicate_count > 0:
                message += f' ({duplicate_count} duplicate)'
            
            update_status(3, 'completed', message, 60)
            
            # ===== STEP 3: ARTICOLI (se richiesto) =====
            articles_generated = 0
            if generate_articles:
                update_status(4, 'processing', 'Generazione articoli AI...', 75)
                
                try:
                    from utils.perplexity_client import PerplexityClient
                    perplexity = PerplexityClient()
                    
                    for i, (match, data) in enumerate(saved_matches):
                        try:
                            progress = 75 + int((i / len(saved_matches)) * 15)
                            update_status(4, 'processing', f'Articolo {i+1}/{len(saved_matches)}', progress)
                            
                            article_content = perplexity.generate_article(data)
                            
                            article = Article(
                                match_id=match.id,
                                title=f"{match.home_team} vs {match.away_team}: Cronaca e Analisi",
                                content=article_content
                            )
                            
                            db.session.add(article)
                            articles_generated += 1
                            
                        except Exception as e:
                            print(f"❌ Errore articolo: {e}")
                    
                    db.session.commit()
                    
                except ImportError:
                    print("⚠️ PerplexityClient non disponibile")
                
                update_status(4, 'completed', f'Generati {articles_generated} articoli', 90)
            
            # ===== STEP 4: CLASSIFICA (se richiesto) =====
            if update_standings:
                update_status(5, 'processing', 'Aggiornamento classifica...', 95)
                
                try:
                    calculate_standings()
                    update_status(5, 'completed', 'Classifica aggiornata', 98)
                except Exception as e:
                    print(f"⚠️ Errore classifica: {e}")
            
            # ===== COMPLETAMENTO =====
            processing_status[session_id].update({
                'completed': True,
                'success': True,
                'gameweek': int(gameweek),
                'matches_processed': len(saved_matches),
                'articles_generated': articles_generated
            })
            
            update_status(5, 'completed', 'Elaborazione completata!', 100)
            
            print(f"🎉 PROCESSO COMPLETATO:")
            print(f"  📝 Partite elaborate: {len(saved_matches)}")
            print(f"  📰 Articoli generati: {articles_generated}")
            
    except Exception as e:
        print(f"💥 ERRORE GENERALE: {e}")
        
        import traceback
        traceback.print_exc()
        
        update_status(0, 'error', f'Errore: {str(e)}', 0, 
                     completed=True, success=False, error=str(e))



app = create_app()

if __name__ == '__main__':
    debug_mode = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    port = int(os.getenv('FLASK_PORT', 5000))
    app.run(debug=debug_mode, host='0.0.0.0', port=port)
