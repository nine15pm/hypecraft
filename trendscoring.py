import requests
import utils
from datetime import datetime, timezone

#CONFIGS
##############################################################################################
TW_HOST = 'twitter154.p.rapidapi.com'
TW_SEARCH_ENDPOINT = 'https://twitter154.p.rapidapi.com/search/search'
TW_TOKEN = utils.read_secrets('RAPID_API_TW_TOKEN')
DATESTR_TODAY = datetime.today().strftime('%Y-%m-%d')
TW_HEADERS = headers = {
	'X-RapidAPI-Key': TW_TOKEN,
	'X-RapidAPI-Host': TW_HOST
}
DATE_FORMAT = "%a %b %d %H:%M:%S %z %Y"

#params for popularity score calc
VIEWS_WEIGHT = 0.4
LIKES_WEIGHT = 0.4
SCALING_FACTOR = 1e4

#SEARCH TWITTER
##############################################################################################
#get top X tweets for a given search query
def searchTwitter(query, max_results=10, min_date=DATESTR_TODAY, section='top', min_likes=1, min_retweets=1, language='en'):
    params = {
        'query': query,
        'limit': max_results,
        'start_date': min_date,
        'section': section,
        'min_retweets': min_retweets,
        'min_likes': min_likes,
        'language': language
    }
    response = requests.get(TW_SEARCH_ENDPOINT, headers=TW_HEADERS, params=params)
    if response.status_code != 200:
        raise Exception(response.status_code, response.text)
    return response.json()['results']

#TRENDING SCORE
##############################################################################################
#calc score to determine popularity of news story
def calcTrendScore(story_query):
    top_tweets = searchTwitter(query=story_query, max_results=10, min_date=DATESTR_TODAY)
    trend_score = 0.0
    for tweet in top_tweets:
        create_time = datetime.strptime(tweet['creation_date'], DATE_FORMAT)
        tweet_lifetime = (datetime.now(timezone.utc) - create_time).total_seconds() / 3600 #how many hours tweet has been up
        trend_score += (VIEWS_WEIGHT*tweet['views'] + LIKES_WEIGHT*tweet['favorite_count']) / (tweet_lifetime * SCALING_FACTOR)
    return trend_score