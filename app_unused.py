import os
import sqlite3
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
            total_shots INTEGER NOT NULL DEFAULT 0,
            avg_click_speed REAL NOT NULL DEFAULT 0,
            accuracy_pct REAL NOT NULL DEFAULT 0,
            bullseye_pct REAL NOT NULL DEFAULT 0,
            miss_interval REAL NOT NULL DEFAULT 0,
            played_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (player_id) REFERENCES players (id)
        )
    ''')
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
#  AI Archetype Engine
# ─────────────────────────────────────────────

ARCHETYPES = [
    {
        "id": "sniper_god",
        "title": "🎯 Sniper God",
        "description": "Cold. Calculated. Lethal. Your precision defies physics — most shots land dead center while the rest never miss the board.",
        "tip": "Keep pushing your bullseye ratio. You're already elite; perfection is one session away.",
        "condition": lambda s: s["bullseye_pct"] >= 40 and s["accuracy_pct"] >= 85
    },
    {
        "id": "the_flash",
        "title": "⚡ The Flash",
        "description": "Nobody clicks faster. Your reaction speed is inhuman — the target barely moves before you've already fired.",
        "tip": "Speed is your superpower. Work on precision next; a fast AND accurate shooter is unstoppable.",
        "condition": lambda s: s["avg_click_speed"] <= 1.2 and s["total_shots"] >= 10
    },
    {
        "id": "iron_wall",
        "title": "🛡️ Iron Wall",
        "description": "Patience incarnate. You almost never miss — and when you do, it haunts you. Consistency is your weapon.",
        "tip": "Your miss rate is extremely low. Try pushing your speed to climb the leaderboard even higher.",
        "condition": lambda s: s["misses"] <= 1 and s["total_shots"] >= 8
    },
    {
        "id": "the_marksman",
        "title": "🔫 The Marksman",
        "description": "Methodical and reliable. High accuracy, steady rhythm — you make it look easy.",
        "tip": "Try to increase your click speed without sacrificing accuracy. That's the path to the top.",
        "condition": lambda s: s["accuracy_pct"] >= 75 and s["avg_click_speed"] <= 2.0
    },
    {
        "id": "the_speedrunner",
        "title": "🏃 The Speedrunner",
        "description": "You play like you're late to something. Aggressive clicks, high volume — sheer speed keeps your score up.",
        "tip": "Slow down just a little before firing. A 10% accuracy gain will more than compensate for the slower pace.",
        "condition": lambda s: s["avg_click_speed"] <= 1.5 and s["accuracy_pct"] < 70
    },
    {
        "id": "bullseye_hunter",
        "title": "🌟 Bullseye Hunter",
        "description": "You live for the gold ring. Others aim to hit — you aim to dominate. Bullseye or nothing.",
        "tip": "Amazing center accuracy! Work on keeping this up even as target speed increases later in the game.",
        "condition": lambda s: s["bullseye_pct"] >= 30
    },
    {
        "id": "steady_hand",
        "title": "✋ Steady Hand",
        "description": "Calm under pressure. Your shot timing is remarkably consistent — no panic, no rush.",
        "tip": "Great composure! Try targeting the bullseye more deliberately to convert consistency into higher scores.",
        "condition": lambda s: s["miss_interval"] >= 20 and s["accuracy_pct"] >= 60
    },
    {
        "id": "the_rookie",
        "title": "🌱 The Rookie",
        "description": "Everyone starts somewhere. You've got the spirit — now the board wants your precision.",
        "tip": "Focus on clicking only when you're sure it's a hit. Fewer shots, higher accuracy = way more points.",
        "condition": lambda s: True  # fallback
    }
]


def compute_archetype(stats: dict) -> dict:
    """Return the first matching archetype for a given stats dict."""
    for arch in ARCHETYPES:
        if arch["condition"](stats):
            return {
                "id": arch["id"],
                "title": arch["title"],
                "description": arch["description"],
                "tip": arch["tip"]
            }
    return {
        "id": "the_rookie",
        "title": "🌱 The Rookie",
        "description": "Everyone starts somewhere. You've got the spirit — now the board wants your precision.",
        "tip": "Focus on clicking only when you're sure it's a hit. Fewer shots, higher accuracy = way more points."
    }


# ─────────────────────────────────────────────
#  Routes
# ─────────────────────────────────────────────

@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')


@app.route('/api/players', methods=['GET'])
def list_players():
    conn = get_db()
    players = conn.execute('SELECT id, name FROM players ORDER BY name').fetchall()
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
        # BUG FIX: player exists → just return their data instead of error
        player = conn.execute('SELECT id, name FROM players WHERE name = ?', (name,)).fetchone()
        conn.close()
        if player:
            return jsonify({'id': player['id'], 'name': player['name']}), 200
        return jsonify({'error': 'Player name already taken'}), 409
    finally:
        try:
            conn.close()
        except Exception:
            pass


@app.route('/api/players/<int:player_id>')
def get_player_by_id(player_id):
    """BUG FIX: loginPlayer() passes an ID (int), not a name."""
    conn = get_db()
    player = conn.execute('SELECT id, name FROM players WHERE id = ?', (player_id,)).fetchone()
    conn.close()
    if player:
        return jsonify({'id': player['id'], 'name': player['name']})
    return jsonify({'error': 'Player not found'}), 404


@app.route('/api/players/by-name/<name>')
def get_player_by_name(name):
    conn = get_db()
    player = conn.execute('SELECT id, name FROM players WHERE name = ?', (name,)).fetchone()
    conn.close()
    if player:
        return jsonify({'id': player['id'], 'name': player['name']})
    return jsonify({'error': 'Player not found'}), 404


@app.route('/api/scores', methods=['POST'])
def save_score():
    data = request.get_json()

    required = ['player_id', 'score', 'misses', 'duration',
                'total_shots', 'avg_click_speed', 'accuracy_pct',
                'bullseye_pct', 'miss_interval']

    for field in required:
        if data.get(field) is None:
            return jsonify({'error': f'Missing field: {field}'}), 400

    stats = {
        'misses': data['misses'],
        'total_shots': data['total_shots'],
        'avg_click_speed': data['avg_click_speed'],
        'accuracy_pct': data['accuracy_pct'],
        'bullseye_pct': data['bullseye_pct'],
        'miss_interval': data['miss_interval'],
    }
    archetype = compute_archetype(stats)

    conn = get_db()
    cursor = conn.execute(
        '''INSERT INTO scores
           (player_id, score, misses, duration, total_shots,
            avg_click_speed, accuracy_pct, bullseye_pct, miss_interval)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (data['player_id'], data['score'], data['misses'], data['duration'],
         data['total_shots'], data['avg_click_speed'], data['accuracy_pct'],
         data['bullseye_pct'], data['miss_interval'])
    )
    conn.commit()
    conn.close()

    return jsonify({'id': cursor.lastrowid, 'success': True, 'archetype': archetype})


@app.route('/api/leaderboard')
def leaderboard():
    conn = get_db()
    # Pull the best-score row per player (all metrics from that run)
    results = conn.execute('''
        SELECT
            p.name,
            s.score        AS best_score,
            s.misses,
            s.total_shots,
            s.avg_click_speed,
            s.accuracy_pct,
            s.bullseye_pct,
            s.miss_interval,
            COUNT(s2.id)   AS games_played
        FROM players p
        INNER JOIN scores s ON s.player_id = p.id
            AND s.score = (SELECT MAX(s3.score) FROM scores s3 WHERE s3.player_id = p.id)
        INNER JOIN scores s2 ON s2.player_id = p.id
        GROUP BY p.id, p.name, s.score, s.misses, s.total_shots,
                 s.avg_click_speed, s.accuracy_pct, s.bullseye_pct, s.miss_interval
        ORDER BY best_score DESC
        LIMIT 20
    ''').fetchall()
    conn.close()

    rows = []
    for r in results:
        stats = {
            'misses': r['misses'],
            'total_shots': r['total_shots'],
            'avg_click_speed': r['avg_click_speed'],
            'accuracy_pct': r['accuracy_pct'],
            'bullseye_pct': r['bullseye_pct'],
            'miss_interval': r['miss_interval'],
        }
        archetype = compute_archetype(stats)
        rows.append({
            'name': r['name'],
            'best_score': r['best_score'],
            'games_played': r['games_played'],
            'avg_click_speed': round(r['avg_click_speed'], 2),
            'accuracy_pct': round(r['accuracy_pct'], 1),
            'bullseye_pct': round(r['bullseye_pct'], 1),
            'miss_interval': round(r['miss_interval'], 1),
            'archetype': archetype,
        })
    return jsonify(rows)


if __name__ == '__main__':
    init_db()
    app.run(debug=True)