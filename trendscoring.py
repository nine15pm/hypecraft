import requests
import utils
from datetime import datetime, timezone

#CONFIGS
##############################################################################################
TW_HOST = 'twitter-api45.p.rapidapi.com'
TW_SEARCH_ENDPOINT = 'https://twitter-api45.p.rapidapi.com/search.php'
TW_TOKEN = utils.read_secrets('RAPID_API_TW_TOKEN')
DATESTR_TODAY = datetime.today().strftime('%Y-%m-%d')
TW_HEADERS = headers = {
	'X-RapidAPI-Key': TW_TOKEN,
	'X-RapidAPI-Host': TW_HOST
}
DATE_FORMAT = "%a %b %d %H:%M:%S %z %Y"

#params for popularity score calc
VIEWS_WEIGHT = 0.5
LIKES_WEIGHT = 0.5
SCALING_FACTOR = 1

#SEARCH TWITTER
##############################################################################################
#get top X tweets for a given search query
def searchTwitter(search_text, min_date=DATESTR_TODAY, search_type='top', min_likes=10):
    #construct query
    query = f'{search_text} since:{min_date} min_faves:{min_likes}'

    params = {
        'query': query,
        'search_type': search_type
    }
    response = requests.get(TW_SEARCH_ENDPOINT, headers=TW_HEADERS, params=params)
    if response.status_code != 200:
        raise Exception(response.status_code, response.text)
    return response.json()['timeline']

#TRENDING SCORE
##############################################################################################
#calc score to determine popularity of news story
def calcTrendScore(story_query, sample_size, min_date):
    top_tweets = searchTwitter(search_text=story_query, min_date=min_date)
    if len(top_tweets) > sample_size:
        top_tweets = top_tweets[:sample_size]
    trend_score = 0.0
    for tweet in top_tweets:
        create_time = datetime.strptime(tweet['creation_date'], DATE_FORMAT)
        tweet_lifetime = (datetime.now(timezone.utc) - create_time).total_seconds() / 3600 #how many hours tweet has been up
        trend_score += (VIEWS_WEIGHT*tweet['views'] + LIKES_WEIGHT*tweet['favorite_count']) / (tweet_lifetime * SCALING_FACTOR)
        print(f'QA - LIFETIME: {tweet_lifetime} hrs, VIEWS: {tweet['views']}, LIKES: {tweet['favorite_count']}')
    #average trend score by num tweets
    trend_score = trend_score / len(top_tweets)
    return trend_score