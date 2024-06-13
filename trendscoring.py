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
TW_DATE_FORMAT = "%a %b %d %H:%M:%S %z %Y"

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
    print(query)
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
def calcTrendScore(queries_list, sample_size, min_datetime):
    top_tweets = []
    #iterate through queries list and try search
    for query in queries_list:
        try:
            results = searchTwitter(search_text=query['query'], min_date=min_datetime.strftime('%Y-%m-%d'))
            if len(results) > sample_size:
                top_tweets += results[:sample_size]
                break
            else:
                top_tweets += results
        except requests.exceptions.JSONDecodeError:
            print('error in Tweet API response')
            return -1

    #check if no results, return -1 to indicate no valid score
    if len(top_tweets) == 0:
        return -1

    trend_score = 0.0
    for tweet in top_tweets:
        create_time = datetime.strptime(tweet['created_at'], TW_DATE_FORMAT)
        tweet_lifetime = (datetime.now(timezone.utc) - create_time).total_seconds() / 3600 #how many hours tweet has been up
        trend_score += (VIEWS_WEIGHT*float(tweet['views']) + LIKES_WEIGHT*tweet['favorites']) / (tweet_lifetime * SCALING_FACTOR)
    #average trend score by num tweets
    trend_score = trend_score / len(top_tweets)
    print(f'Num tweets {len(top_tweets)}')
    print(f'{trend_score}')
    return trend_score