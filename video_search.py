import requests
import sys
import json
import os
import argparse
from urllib.parse import quote
import time
import webbrowser
from datetime import datetime

def load_json_data():
    data_dir = os.path.join(os.path.dirname(__file__), 'data')
    genres_path = os.path.join(data_dir, 'genres.json')
    countries_path = os.path.join(data_dir, 'countries.json')
    
    with open(genres_path, 'r', encoding='utf-8') as f:
        genres_data = json.load(f)
        genres = genres_data.get('data', [])
    
    with open(countries_path, 'r', encoding='utf-8') as f:
        countries_data = json.load(f)
        countries = countries_data.get('data', [])
    
    return genres, countries

def safe_get(obj, key, default=None):
    """Safely get a value from a dictionary or return default"""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return default

def process_response(response_data):
    """Process the API response and return a list of items"""
    if isinstance(response_data, str):
        try:
            # Try to parse the string as JSON
            response_data = json.loads(response_data)
        except json.JSONDecodeError:
            print(f"Response is a string but not valid JSON: {response_data[:100]}...")
            return []
    
    if isinstance(response_data, list):
        return response_data
    elif isinstance(response_data, dict):
        # Check if the response has a data field
        if 'data' in response_data:
            return response_data['data']
        # Check for other common response formats
        for key in ['movies', 'series', 'items', 'results']:
            if key in response_data:
                return response_data[key]
    
    print(f"Unexpected response format: {type(response_data)}")
    return []

def extract_media_details(media_item, media_type, genre_title):
    """Extract and format media details from API response"""
    if not isinstance(media_item, dict):
        return None
        
    # Extract basic info
    title = safe_get(media_item, 'title', '')
    year = safe_get(media_item, 'year', '')
    poster = safe_get(media_item, 'poster', '')
    sources = safe_get(media_item, 'sources', [])
    
    # Extract description or try to compile one from other fields
    description = safe_get(media_item, 'description', '')
    
    # If no description is provided but we have other details, create one
    if not description:
        details = []
        
        # Try to extract common fields that might be in the response
        original_name = safe_get(media_item, 'originalName', '')
        if original_name:
            details.append(f"نام اصلی: {original_name}")
            
        rating = safe_get(media_item, 'imdb', '') or safe_get(media_item, 'rating', '')
        if rating:
            details.append(f"امتیاز: {rating}/ 10")
            
        persian_name = safe_get(media_item, 'persianName', '') or safe_get(media_item, 'persian_title', '')
        if persian_name:
            details.append(f"نام پارسی: {persian_name}")
            
        genres = safe_get(media_item, 'genres', [])
        if genres and isinstance(genres, list):
            genres_str = ', '.join(genres)
            details.append(f"ژانر: {genres_str}")
        elif genre_title:
            details.append(f"ژانر: {genre_title}")
            
        if year:
            details.append(f"سال تولید: {year}")
            
        country = safe_get(media_item, 'country', '')
        if country:
            details.append(f"محصول: {country}")
            
        language = safe_get(media_item, 'language', '')
        if language:
            details.append(f"زبان: {language}")
            
        age_rating = safe_get(media_item, 'ageRating', '')
        if age_rating:
            details.append(f"رده سنی: {age_rating}")
            
        format_type = safe_get(media_item, 'format', '')
        if format_type:
            details.append(f"فرمت: {format_type}")
            
        quality = safe_get(media_item, 'quality', '')
        if quality:
            details.append(f"کیفیت: {quality}")
            
        size = safe_get(media_item, 'size', '')
        if size:
            details.append(f"حجم: {size}")
            
        plot = safe_get(media_item, 'plot', '') or safe_get(media_item, 'summary', '')
        if plot:
            details.append(f"\nخلاصه داستان:\n{plot}")
            
        # Join all details into a description
        if details:
            description = '\n'.join(details)
    
    return {
        'title': title,
        'year': year,
        'genre': genre_title,
        'type': media_type,
        'sources': sources,
        'poster': poster,
        'description': description,
    }

def search_movies(query, genre_id=None, country_id=None):
    # Base URL for movie search
    base_url = "http://slamtiomid.info/api/movie/by/filtres/{genre_id}/year/{page_num}/4F5A9C3D9A86FA54EACEDDD635185/"
    
    try:
        genres, _ = load_json_data()
        results = []
        
        # If genre_id is specified, only search in that genre
        search_genres = [g for g in genres if genre_id is None or g.get('id') == genre_id]
        
        for genre in search_genres:
            genre_id = genre.get('id')
            genre_title = genre.get('title', '')
            if genre_id:
                page = 0
                while True:
                    search_url = base_url.format(genre_id=genre_id, page_num=page)
                    print(f"Searching page {page} for movies in genre {genre.get('title')}...")
                    
                    response = requests.get(search_url)
                    if response.status_code == 200:
                        try:
                            response_data = response.json()
                            movies = process_response(response_data)
                            
                            if not movies:  # Empty response means we've reached the end
                                break
                                
                            for movie in movies:
                                if not isinstance(movie, dict):
                                    continue
                                    
                                title = safe_get(movie, 'title', '')
                                if query.lower() in title.lower() or query.lower() == title.lower():
                                    movie_details = extract_media_details(movie, 'Movie', genre_title)
                                    if movie_details:
                                        results.append(movie_details)
                                        if query.lower() == title.lower():  # Exact match
                                            return results  # Return immediately for exact match
                            page += 1
                            time.sleep(0.5)  # Add a small delay to avoid overwhelming the server
                        except json.JSONDecodeError:
                            print(f"Invalid JSON response for page {page}")
                            print(f"Response content: {response.text[:200]}...")
                            break
                    else:
                        print(f"Error fetching page {page}. Status code: {response.status_code}")
                        print(f"Response content: {response.text[:200]}...")
                        break
    except Exception as e:
        print(f"Error searching movies: {str(e)}")
        import traceback
        traceback.print_exc()
    
    return results

def search_series(query, genre_id=None, country_id=None):
    # Base URL for series search
    base_url = "http://slamtiomid.info/api/serie/by/filtres/{genre_id}/year/{page_num}/4F5A9C3D9A86FA54EACEDDD635185/"
    
    try:
        genres, _ = load_json_data()
        results = []
        
        # If genre_id is specified, only search in that genre
        search_genres = [g for g in genres if genre_id is None or g.get('id') == genre_id]
        
        for genre in search_genres:
            genre_id = genre.get('id')
            genre_title = genre.get('title', '')
            if genre_id:
                page = 0
                while True:
                    search_url = base_url.format(genre_id=genre_id, page_num=page)
                    print(f"Searching page {page} for series in genre {genre.get('title')}...")
                    
                    response = requests.get(search_url)
                    if response.status_code == 200:
                        try:
                            response_data = response.json()
                            series = process_response(response_data)
                            
                            if not series:  # Empty response means we've reached the end
                                break
                                
                            for serie in series:
                                if not isinstance(serie, dict):
                                    continue
                                    
                                title = safe_get(serie, 'title', '')
                                if query.lower() in title.lower() or query.lower() == title.lower():
                                    serie_details = extract_media_details(serie, 'Series', genre_title)
                                    if serie_details:
                                        results.append(serie_details)
                                        if query.lower() == title.lower():  # Exact match
                                            return results  # Return immediately for exact match
                            page += 1
                            time.sleep(0.5)  # Add a small delay to avoid overwhelming the server
                        except json.JSONDecodeError:
                            print(f"Invalid JSON response for page {page}")
                            print(f"Response content: {response.text[:200]}...")
                            break
                    else:
                        print(f"Error fetching page {page}. Status code: {response.status_code}")
                        print(f"Response content: {response.text[:200]}...")
                        break
    except Exception as e:
        print(f"Error searching series: {str(e)}")
        import traceback
        traceback.print_exc()
    
    return results

def list_genres_and_countries():
    genres, countries = load_json_data()
    
    print("\nAvailable Genres:")
    for genre in genres:
        print(f"ID: {genre.get('id')} - {genre.get('title')}")
    
    print("\nAvailable Countries:")
    for country in countries:
        print(f"ID: {country.get('id')} - {country.get('title')}")

def parse_source(source):
    """Parse a source object into type, quality, and URL"""
    if isinstance(source, str):
        # Handle legacy string format
        return {
            'type': 'unknown',
            'quality': 'unknown',
            'url': source
        }
    elif isinstance(source, dict):
        # Handle structured object format
        quality = source.get('quality', 'unknown')
        source_type = source.get('type', 'unknown')
        url = source.get('url', '')
        
        # Map quality values to standard formats
        quality_mapping = {
            'تیزر': 'Trailer',
            '480 زیرنویس': '480p',
            '720 زیرنویس': '720p',
            '1080 زیرنویس': '1080p',
            '1080 FULLHD زیرنویس': '1080p'
        }
        
        # Map type values to standard formats
        type_mapping = {
            'mp4': 'stream',
            'mkv': 'download'
        }
        
        return {
            'type': type_mapping.get(source_type.lower(), source_type),
            'quality': quality_mapping.get(quality, quality),
            'url': url
        }
    
    return None

def generate_html(results):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Video Search Results</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 20px;
                background-color: #f5f5f5;
            }}
            .result {{
                background-color: white;
                border-radius: 8px;
                padding: 20px;
                margin-bottom: 20px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            .title {{
                color: #2c3e50;
                font-size: 24px;
                margin-bottom: 10px;
            }}
            .info {{
                color: #7f8c8d;
                margin-bottom: 10px;
            }}
            .poster {{
                max-width: 200px;
                margin-bottom: 10px;
            }}
            .sources {{
                margin-top: 15px;
            }}
            .source {{
                display: block;
                padding: 8px;
                margin-bottom: 8px;
                background-color: #f8f9fa;
                border-radius: 4px;
                text-decoration: none;
                color: #2c3e50;
            }}
            .source:hover {{
                background-color: #e9ecef;
            }}
            .source-type {{
                display: inline-block;
                padding: 2px 6px;
                border-radius: 3px;
                font-size: 12px;
                margin-right: 8px;
            }}
            .source-quality {{
                display: inline-block;
                padding: 2px 6px;
                border-radius: 3px;
                font-size: 12px;
                margin-right: 8px;
                background-color: #3498db;
                color: white;
            }}
            .download {{
                background-color: #e74c3c;
                color: white;
            }}
            .stream {{
                background-color: #2ecc71;
                color: white;
            }}
            .torrent {{
                background-color: #f39c12;
                color: white;
            }}
            .unknown {{
                background-color: #95a5a6;
                color: white;
            }}
            .type-badge {{
                display: inline-block;
                padding: 3px 8px;
                border-radius: 4px;
                font-size: 12px;
                margin-right: 10px;
            }}
            .movie {{
                background-color: #e74c3c;
                color: white;
            }}
            .series {{
                background-color: #2ecc71;
                color: white;
            }}
        </style>
    </head>
    <body>
        <h1>Video Search Results</h1>
        <p>Search performed at: {timestamp}</p>
    """
    
    for result in results:
        html += f"""
        <div class="result">
            <div class="title">
                <span class="type-badge {result['type'].lower()}">{result['type']}</span>
                {result['title']}
            </div>
            <div class="info">
                Year: {result['year']}<br>
                Genre: {result['genre']}
            </div>
        """
        
        if result.get('poster'):
            html += f'<img class="poster" src="{result["poster"]}" alt="Poster"><br>'
            
        if result.get('sources'):
            html += "<div class='sources'>Sources:<br>"
            for source in result['sources']:
                parsed_source = parse_source(source)
                if parsed_source:
                    html += f"""
                    <a class="source" href="{parsed_source['url']}" target="_blank">
                        <span class="source-type {parsed_source['type']}">{parsed_source['type'].upper()}</span>
                        <span class="source-quality">{parsed_source['quality']}</span>
                        {parsed_source['url']}
                    </a>
                    """
            html += "</div>"
            
        html += "</div>"
    
    html += """
    </body>
    </html>
    """
    
    return html

def main():
    parser = argparse.ArgumentParser(description='Search for movies and series')
    parser.add_argument('query', nargs='+', help='Search query')
    parser.add_argument('--genre', type=int, help='Filter by genre ID')
    parser.add_argument('--country', type=int, help='Filter by country ID')
    parser.add_argument('--type', type=str, help='Filter by type (movie or series)')
    parser.add_argument('--list', action='store_true', help='List all available genres and countries')
    
    args = parser.parse_args()
    
    if args.list:
        list_genres_and_countries()
        return
    
    query = ' '.join(args.query)
    print(f"Searching for: {query}")
    if args.genre:
        print(f"Filtering by genre ID: {args.genre}")
    if args.country:
        print(f"Filtering by country ID: {args.country}")
    
    results = []
    if not args.type or args.type == 'movie':
        # Search in movies
        print("\nSearching in Movies...")
        movie_results = search_movies(query, args.genre, args.country)
        results.extend(movie_results)
    
    if not args.type or args.type == 'series':
        # Search in series
        print("\nSearching in Series...")
        series_results = search_series(query, args.genre, args.country)
        results.extend(series_results)
    
    if not results:
        print("\nNo results found.")
        return
    
    # Generate HTML
    html_content = generate_html(results)
    
    # Save HTML file
    output_dir = os.path.join(os.path.dirname(__file__), 'output')
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f'search_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.html')
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    # Open in browser
    print(f"\nOpening results in browser: {output_file}")
    webbrowser.open('file://' + os.path.abspath(output_file))

if __name__ == "__main__":
    main() 