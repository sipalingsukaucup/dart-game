import os
import sqlite3
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__, static_folder=os.path.abspath(os.path.join(os.path.dirname(__file__), 'static')))

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dart_game.db')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL,
            score INTEGER NOT NULL,
            misses INTEGER NOT NULL,
            duration INTEGER NOT NULL,
            played_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (player_id) REFERENCES players (id)
        )
    ''')
    conn.commit()
    conn.close()


@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')


@app.route('/api/players', methods=['GET'])
def list_players():
    conn = get_db()
    players = conn.execute('SELECT id, name FROM players').fetchall()
    conn.close()
    return jsonify([{'id': p['id'], 'name': p['name']} for p in players])


@app.route('/api/players', methods=['POST'])
def create_player():
    data = request.get_json()
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Name is required'}), 400

    conn = get_db()
    try:
        cursor = conn.execute('INSERT INTO players (name) VALUES (?)', (name,))
        conn.commit()
        return jsonify({'id': cursor.lastrowid, 'name': name}), 201
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Player name already taken'}), 409
    finally:
        conn.close()


@app.route('/api/players/<name>')
def get_player(name):
    conn = get_db()
    player = conn.execute('SELECT id, name FROM players WHERE name = ?', (name,)).fetchone()
    conn.close()
    if player:
        return jsonify({'id': player['id'], 'name': player['name']})
    return jsonify({'error': 'Player not found'}), 404


@app.route('/api/scores', methods=['POST'])
def save_score():
    data = request.get_json()
    player_id = data.get('player_id')
    score = data.get('score')
    misses = data.get('misses')
    duration = data.get('duration')

    if player_id is None or score is None or misses is None or duration is None:
        return jsonify({'error': 'All fields are required'}), 400

    conn = get_db()
    cursor = conn.execute(
        'INSERT INTO scores (player_id, score, misses, duration) VALUES (?, ?, ?, ?)',
        (player_id, score, misses, duration)
    )
    conn.commit()
    conn.close()
    return jsonify({'id': cursor.lastrowid, 'success': True})


@app.route('/api/leaderboard')
def leaderboard():
    conn = get_db()
    results = conn.execute('''
        SELECT p.name, MAX(s.score) as best_score, COUNT(s.id) as games_played
        FROM players p
        INNER JOIN scores s ON p.id = s.player_id
        GROUP BY p.id, p.name
        ORDER BY best_score DESC
        LIMIT 20
    ''').fetchall()
    conn.close()
    return jsonify([{
        'name': r['name'],
        'best_score': r['best_score'] if r['best_score'] else 0,
        'games_played': r['games_played'] if r['games_played'] else 0
    } for r in results])


if __name__ == '__main__':
    init_db()
    app.run(debug=True)