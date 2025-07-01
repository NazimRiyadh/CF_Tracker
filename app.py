from flask import Flask, render_template, request, send_file, redirect, url_for, session
import requests
import csv
import io
import json
import os
from datetime import datetime, timedelta
from collections import defaultdict
import random
from collections import defaultdict

app = Flask(__name__)
app.secret_key = 'cf-tracker-secret-key'

NOTES_FILE = 'notes.json'

# Load notes from file if exists with safe loading
if os.path.exists(NOTES_FILE):
    try:
        with open(NOTES_FILE, 'r') as f:
            user_notes = json.load(f)
    except (json.JSONDecodeError, IOError):
        user_notes = {}
else:
    user_notes = {}

def save_notes():
    try:
        with open(NOTES_FILE, 'w') as f:
            json.dump(user_notes, f, indent=4)
    except IOError:
        pass  # You may want to log this error

def get_rating_color(rating):
    """Get color class based on Codeforces rating"""
    if rating == 'N/A' or rating is None:
        return 'unrated'
    try:
        rating = int(rating)
    except (ValueError, TypeError):
        return 'unrated'
    if rating < 1200:
        return 'newbie'
    elif rating < 1400:
        return 'pupil'
    elif rating < 1600:
        return 'specialist'
    elif rating < 1900:
        return 'expert'
    elif rating < 2100:
        return 'candidate-master'
    elif rating < 2300:
        return 'master'
    elif rating < 2400:
        return 'international-master'
    elif rating < 2600:
        return 'grandmaster'
    elif rating < 3000:
        return 'international-grandmaster'
    else:
        return 'legendary-grandmaster'

def get_rank_color(rank):
    """Get color class based on Codeforces rank"""
    rank_colors = {
        'newbie': 'newbie',
        'pupil': 'pupil',
        'specialist': 'specialist',
        'expert': 'expert',
        'candidate master': 'candidate-master',
        'master': 'master',
        'international master': 'international-master',
        'grandmaster': 'grandmaster',
        'international grandmaster': 'international-grandmaster',
        'legendary grandmaster': 'legendary-grandmaster'
    }
    return rank_colors.get(rank.lower(), 'unrated')

import random
from collections import defaultdict

import random
from collections import defaultdict

def generate_recommendations(handle):
    problems, error = fetch_submissions(handle)
    if error or not problems:
        return []

    solved = {pid: p for pid, p in problems.items() if p['status'] == 'OK'}
    solved_ratings = [int(p['rating']) for p in solved.values() if isinstance(p['rating'], int)]
    solved_tags = [tag for p in solved.values() for tag in p['tags'] if tag]

    if not solved_ratings:
        return []

    avg_rating = sum(solved_ratings) // len(solved_ratings)

    # Count tag frequencies and pick top 5 favorite tags
    tag_freq = defaultdict(int)
    for tag in solved_tags:
        tag_freq[tag] += 1
    preferred_tags = sorted(tag_freq.items(), key=lambda x: x[1], reverse=True)
    top_tags = {tag for tag, _ in preferred_tags[:5]}

    # Fetch all problems from CF
    all_problems_url = "https://codeforces.com/api/problemset.problems"
    resp = requests.get(all_problems_url)
    if resp.status_code != 200:
        return []

    data = resp.json()
    if data['status'] != 'OK':
        return []

    all_problems = data['result']['problems']

    # Filtering rules
    candidates = []
    for p in all_problems:
        pid = f"{p['contestId']}-{p['index']}"
        rating = p.get('rating')
        tags = p.get('tags', [])

        if pid in solved:
            continue
        if not isinstance(rating, int):
            continue
        if not (avg_rating - 200 <= rating <= avg_rating + 200):
            continue
        if top_tags and not top_tags.intersection(tags):
            continue

        candidates.append({
            'name': p['name'],
            'title': p['name'],
            'rating': rating,
            'tags': tags,
            'url': f"https://codeforces.com/problemset/problem/{p['contestId']}/{p['index']}"
        })

    # If no candidates with tags, relax tag filter
    if not candidates:
        for p in all_problems:
            pid = f"{p['contestId']}-{p['index']}"
            rating = p.get('rating')

            if pid in solved or not isinstance(rating, int):
                continue
            if avg_rating - 200 <= rating <= avg_rating + 200:
                candidates.append({
                    'name': p['name'],
                    'title': p['name'],
                    'rating': rating,
                    'tags': p.get('tags', []),
                    'url': f"https://codeforces.com/problemset/problem/{p['contestId']}/{p['index']}"
                })

    # Shuffle candidates to get varied suggestions
    random.shuffle(candidates)

    # Select top 3 diverse problems based on tags to avoid repetition
    selected = []
    used_tags = set()
    for c in candidates:
        if len(selected) == 3:
            break
        if not used_tags.intersection(set(c['tags'])):
            selected.append(c)
            used_tags.update(c['tags'])

    # If less than 3 found by diversity, fill the rest by rating closeness
    if len(selected) < 3:
        for c in candidates:
            if c not in selected:
                selected.append(c)
                if len(selected) == 3:
                    break

    return selected




def calculate_profile_stats(handle):
    """Calculate comprehensive profile statistics"""
    problems, error = fetch_submissions(handle, notes=user_notes)
    if error or not problems:
        return None, error
    
    # Get user contest history
    contest_url = f"https://codeforces.com/api/user.rating?handle={handle}"
    contest_resp = requests.get(contest_url)
    contest_history = []
    if contest_resp.status_code == 200:
        contest_data = contest_resp.json()
        if contest_data['status'] == 'OK':
            contest_history = contest_data['result']
    
    # Basic stats
    total_problems = len(problems)
    solved_problems = len([p for p in problems.values() if p['status'] == 'OK'])
    tried_problems = len([p for p in problems.values() if p['status'] == 'TRIED'])
    
    # Rating distribution
    rating_distribution = defaultdict(int)
    solved_by_rating = defaultdict(int)
    for prob in problems.values():
        if prob['rating'] not in ['N/A', None]:
            try:
                rating = int(prob['rating'])
                rating_range = f"{(rating // 100) * 100}-{(rating // 100) * 100 + 99}"
                rating_distribution[rating_range] += 1
                if prob['status'] == 'OK':
                    solved_by_rating[rating_range] += 1
            except ValueError:
                pass
    
    # Tag analysis
    tag_stats = defaultdict(lambda: {'total': 0, 'solved': 0})
    for prob in problems.values():
        tags = prob.get('tags', [])
        for tag in tags:
            if tag:
                tag_stats[tag]['total'] += 1
                if prob['status'] == 'OK':
                    tag_stats[tag]['solved'] += 1
    
    # Calculate success rate for each tag
    for tag in tag_stats:
        total = tag_stats[tag]['total']
        solved = tag_stats[tag]['solved']
        tag_stats[tag]['success_rate'] = (solved / total * 100) if total > 0 else 0
    
    # Activity analysis
    activity_by_month = defaultdict(int)
    activity_by_day = defaultdict(int)
    current_year = datetime.now().year
    
    for prob in problems.values():
        if prob['status'] == 'OK' and prob.get('date'):
            try:
                date = datetime.strptime(prob['date'], '%Y-%m-%d')
                month_key = f"{date.year}-{date.month:02d}"
                activity_by_month[month_key] += 1
                
                # Last 365 days activity
                if date >= datetime.now() - timedelta(days=365):
                    activity_by_day[prob['date']] += 1
            except:
                pass
    
    # Contest performance
    contest_stats = {
        'total_contests': len(contest_history),
        'rating_changes': [],
        'best_rank': None,
        'worst_rank': None,
        'avg_rating_change': 0
    }
    
    if contest_history:
        rating_changes = [contest['newRating'] - contest['oldRating'] for contest in contest_history]
        contest_stats['rating_changes'] = rating_changes
        contest_stats['avg_rating_change'] = sum(rating_changes) / len(rating_changes)
        
        ranks = [contest.get('rank', float('inf')) for contest in contest_history if contest.get('rank')]
        if ranks:
            contest_stats['best_rank'] = min(ranks)
            contest_stats['worst_rank'] = max(ranks)
    
    # Calculate streaks
    solved_dates = sorted(set(
        datetime.strptime(prob['date'], '%Y-%m-%d').date()
        for prob in problems.values()
        if prob['status'] == 'OK' and prob.get('date')
    ))
    current_streak = 0
    max_streak = 0

    if solved_dates:
        today = datetime.now().date()
        # Calculate current streak by checking backward from today
        day_check = today
        for date in reversed(solved_dates):
            if date == day_check:
                current_streak += 1
                day_check -= timedelta(days=1)
            elif date < day_check:
                break

        # Calculate max streak
        streak = 1
        max_streak = 1
        for i in range(1, len(solved_dates)):
            if (solved_dates[i] - solved_dates[i - 1]).days == 1:
                streak += 1
                max_streak = max(max_streak, streak)
            else:
                streak = 1
        max_streak = max(max_streak, streak)
    
    # Recent activity (last 30 days)
    thirty_days_ago = datetime.now().date() - timedelta(days=30)
    recent_solved = 0
    for prob in problems.values():
        if prob['status'] == 'OK' and prob.get('date'):
            try:
                date = datetime.strptime(prob['date'], '%Y-%m-%d').date()
                if date >= thirty_days_ago:
                    recent_solved += 1
            except:
                pass
    
    stats = {
        'total_problems': total_problems,
        'solved_problems': solved_problems,
        'tried_problems': tried_problems,
        'success_rate': (solved_problems / total_problems * 100) if total_problems > 0 else 0,
        'rating_distribution': dict(rating_distribution),
        'solved_by_rating': dict(solved_by_rating),
        'tag_stats': dict(tag_stats),
        'activity_by_month': dict(activity_by_month),
        'activity_by_day': dict(activity_by_day),
        'contest_stats': contest_stats,
        'current_streak': current_streak,
        'max_streak': max_streak,
        'recent_solved': recent_solved,
        'contest_history': contest_history[-10:]  # Last 10 contests
    }
    
    return stats, None

def fetch_submissions(handle, notes=None):
    url = f"https://codeforces.com/api/user.status?handle={handle}"
    resp = requests.get(url)
    if resp.status_code != 200:
        return None, "Failed to fetch data from Codeforces API."
    data = resp.json()
    if data['status'] != 'OK':
        return None, "Codeforces API returned error."

    if notes is None:
        notes = {}

    problems = {}
    for sub in data['result']:
        prob = sub['problem']
        pid = f"{prob['contestId']}-{prob['index']}"
        rating = prob.get('rating', 'N/A')
        name = prob['name']
        tags = prob.get('tags', [])
        link = f"https://codeforces.com/problemset/problem/{prob['contestId']}/{prob['index']}"
        timestamp = datetime.fromtimestamp(sub['creationTimeSeconds']).strftime('%Y-%m-%d')

        if pid not in problems:
            problems[pid] = {
                'name': name,
                'link': link,
                'tags': tags,
                'rating': rating,
                'status': 'TRIED',
                'note': notes.get(pid, {}).get('note', ''),
                'revise': notes.get(pid, {}).get('revise', False),
                'date': timestamp
            }

        if sub['verdict'] == 'OK':
            problems[pid]['status'] = 'OK'

    return problems, None


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        handle = request.form.get('handle')
        if not handle:
            return render_template('index.html', error="Please enter a Codeforces handle.")
        session['handle'] = handle
        problems, error = fetch_submissions(handle, notes=user_notes)
        if error:
            return render_template('index.html', error=error)
        return render_template('results.html', handle=handle, problems=problems,
                               filter_status='', filter_revise='', filter_tags=[],
                               filter_min_rating='', filter_max_rating='')
    return render_template('index.html')

@app.route('/profile/<handle>')
def profile(handle):
    # Fetch user basic info
    url = f"https://codeforces.com/api/user.info?handles={handle}"
    resp = requests.get(url)
    if resp.status_code != 200:
        return f"Failed to fetch user info for {handle}", 500
    data = resp.json()
    if data['status'] != 'OK' or not data['result']:
        return f"User {handle} not found or API error.", 404

    user_info = data['result'][0]
    
    
    # Add color classes for rating and rank
    user_info['rating_color'] = get_rating_color(user_info.get('rating'))
    user_info['max_rating_color'] = get_rating_color(user_info.get('maxRating'))
    user_info['rank_color'] = get_rank_color(user_info.get('rank', ''))
    user_info['max_rank_color'] = get_rank_color(user_info.get('maxRank', ''))
    
    # Calculate comprehensive stats
    stats, error = calculate_profile_stats(handle)
    if error:
        stats = {}
    # Debug: print activity_by_day to server log
    print('DEBUG: activity_by_day =', stats.get('activity_by_day', {}))
    
    # Format registration date
    if 'registrationTimeSeconds' in user_info:
        reg_date = datetime.fromtimestamp(user_info['registrationTimeSeconds'])
        user_info['registration_date'] = reg_date.strftime('%B %d, %Y')
        user_info['years_active'] = (datetime.now() - reg_date).days // 365
    
    # Format last online
    if 'lastOnlineTimeSeconds' in user_info:
        last_online = datetime.fromtimestamp(user_info['lastOnlineTimeSeconds'])
        user_info['last_online'] = last_online.strftime('%B %d, %Y at %H:%M')
        days_ago = (datetime.now() - last_online).days
        if days_ago == 0:
            user_info['last_online_relative'] = 'Today'
        elif days_ago == 1:
            user_info['last_online_relative'] = 'Yesterday'
        else:
            user_info['last_online_relative'] = f'{days_ago} days ago'

    # Prepare activity JSON for JS heatmap
    activity_json = json.dumps(stats.get('activity_by_day', {}))

    return render_template('profile.html', handle=handle, user_info=user_info, stats=stats, activity_json=activity_json)

@app.route('/results/<handle>')
def results_with_handle(handle):
    problems, error = fetch_submissions(handle, notes=user_notes)
    if error:
        return render_template('index.html', error=error)

    # Get user info for results page
    user_url = f"https://codeforces.com/api/user.info?handles={handle}"
    user_resp = requests.get(user_url)
    user_info = {}
    if user_resp.status_code == 200:
        user_data = user_resp.json()
        if user_data['status'] == 'OK' and user_data['result']:
            user_info = user_data['result'][0]

    # Rating-wise problem count
    rating_counts = defaultdict(int)
    streak_by_day = defaultdict(int)

    for pid, info in problems.items():
        if info.get('status') == 'OK' and info.get('rating') not in [None, 'N/A']:
            rating = str(info['rating'])
            rating_counts[rating] += 1

        if info.get('status') == 'OK' and info.get('date'):
            try:
                date = datetime.strptime(info['date'], '%Y-%m-%d').date()
                streak_by_day[date.isoformat()] += 1
            except:
                pass

    rating_data = sorted([[r, c] for r, c in rating_counts.items()])
    streak_data = sorted([[d, c] for d, c in streak_by_day.items()])

    return render_template('results.html', handle=handle, problems=problems,
                           filter_status='', filter_revise='', filter_tags=[],
                           filter_min_rating='', filter_max_rating='')



@app.route('/submit_notes', methods=['POST'])
def submit_notes():
    handle = request.form.get('handle')
    for key in request.form:
        if key.startswith("note_"):
            pid = key.replace("note_", "")
            note = request.form.get(key, '').strip()
            revise = request.form.get(f"revise_{pid}") == 'on'

            if note or revise:
                user_notes[pid] = {'note': note, 'revise': revise}
            elif pid in user_notes:
                user_notes.pop(pid)
    save_notes()
    return redirect(url_for('results_with_handle', handle=handle))  # ✅ Corrected route



@app.route('/filter', methods=['POST'])
def filter_problems():
    handle = session.get('handle')
    if not handle:
        return redirect(url_for('index'))

    filter_status = request.form.get('filter_status', '')
    filter_revise = request.form.get('filter_revise', '')
    filter_min_rating = request.form.get('filter_min_rating', '')
    filter_max_rating = request.form.get('filter_max_rating', '')
    filter_tags = request.form.getlist('filter_tags')

    problems, error = fetch_submissions(handle, notes=user_notes)
    if error or not problems:
        return redirect(url_for('index'))

    if filter_status == 'unsolved':
        problems = {k: v for k, v in problems.items() if v['status'] != 'OK'}
    if filter_revise == 'yes':
        problems = {k: v for k, v in problems.items() if v['revise']}
    if filter_min_rating:
        try:
            min_r = int(filter_min_rating)
            problems = {k: v for k, v in problems.items() if v['rating'] != 'N/A' and isinstance(v['rating'], int) and v['rating'] >= min_r}
        except ValueError:
            pass
    if filter_max_rating:
        try:
            max_r = int(filter_max_rating)
            problems = {k: v for k, v in problems.items() if v['rating'] != 'N/A' and isinstance(v['rating'], int) and v['rating'] <= max_r}
        except ValueError:
            pass
    if filter_tags:
        problems = {
            k: v for k, v in problems.items()
            if any(tag in v['tags'] for tag in filter_tags)
        }

    return render_template('results.html', handle=handle, problems=problems,
                           filter_status=filter_status, filter_revise=filter_revise,
                           filter_tags=filter_tags, filter_min_rating=filter_min_rating,
                           filter_max_rating=filter_max_rating)

@app.route('/revise_list')
def revise_list():
    handle = session.get('handle')
    if not handle:
        return redirect(url_for('index'))
    problems, error = fetch_submissions(handle, notes=user_notes)
    if error or not problems:
        return redirect(url_for('index'))
    filtered = {k: v for k, v in problems.items() if v['revise']}
    return render_template('results.html', handle=handle, problems=filtered,
                           filter_status='', filter_revise='yes', filter_tags=[],
                           filter_min_rating='', filter_max_rating='')

@app.route('/download_csv/<handle>')
def download_csv(handle):
    problems, error = fetch_submissions(handle, notes=user_notes)
    if error or not problems:
        return redirect(url_for('index'))
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Problem ID', 'Name', 'Link', 'Tags', 'Rating', 'Status', 'Note', 'Revise', 'Date'])
    for pid, info in problems.items():
        writer.writerow([
            pid,
            info['name'],
            info['link'],
            ', '.join(info['tags']) if isinstance(info['tags'], list) else info['tags'],
            info.get('rating', 'N/A'),
            info['status'],
            info.get('note', ''),
            'Yes' if info.get('revise') else 'No',
            info.get('date', '')
        ])
    output.seek(0)
    return send_file(io.BytesIO(output.getvalue().encode()), mimetype='text/csv', as_attachment=True,
                     download_name=f'{handle}_codeforces_problems.csv')

@app.route('/api/profile_chart_data/<handle>')
def profile_chart_data(handle):
    """API endpoint for profile chart data"""
    stats, error = calculate_profile_stats(handle)
    if error:
        return {'error': error}, 400
    return 

@app.route('/suggestions/<handle>')
def suggestions(handle):
    suggestions = generate_recommendations(handle)  # This function must exist
    return render_template('suggestions.html', handle=handle, suggestions=suggestions)


if __name__ == '__main__':
    app.run(debug=True)

