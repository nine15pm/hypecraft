import feedparser
import db
import requests
import requests.auth
import utils
import configs
import time
from datetime import datetime
import json
import ua_generator
import undetected_chromedriver as uc
import trafilatura
from haystack.components.fetchers import LinkContentFetcher
import re

#SHARED FUNCTIONS
###################################################################
#Functions to check if duplicate post already exists in DB
def isDuplicateLink(link):
    filters_self = {
        'post_link': link
    }
    filters_external = {
        'external_link': link
    }
    if db.getFilteredPostIDs(filters=filters_self) != [] or db.getPosts(filters=filters_external) != []:
        return True
    else:
        return False

def isDuplicateText(title=None, post_text=None, external_text=None):
    filters_title = {
        'post_title': title
    }
    filters_post_text = {
        'post_text': post_text
    }
    filters_external_text = {
        'external_parsed_text': external_text
    }
    if title is not None:
        if db.getFilteredPostIDs(filters=filters_title) != []:
            return True
    if post_text is not None and post_text != '':
        if db.getFilteredPostIDs(filters=filters_post_text) != []:
            return True
    if external_text is not None and external_text != '':
        if db.getPosts(filters=filters_external_text) != []:
            return True
    return False

#TEXT EXTRACTION AND HELPER FUNCTIONS
###################################################################

def generateHeaders():
    #generate request headers for simple http request to mimic browser
    ua = ua_generator.generate(device='desktop', platform = ('windows'), browser=('chrome', 'edge'))
    ua.headers.accept_ch('Sec-Ch-Ua-Model, Sec-Ch-Ua-Arch, Sec-Ch-Ua-Bitness, Sec-Ch-Ua-Full-Version, Sec-Ch-Ua-Platform, Sec-Ch-Ua-Wow64, Sec-CH-UA-Platform-Version, Sec-CH-UA-Full-Version-List')
    additional_headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br, zstd',
        'Accept-Language': 'en-US,en;q=0.9',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-User': '1',
        'Upgrade-Insecure-Requests': '1',
        'cache-control': 'max-age=0'
        }
    headers = additional_headers.update(ua.headers.get()) #combine generated headers with additional fixed headers
    return headers

#unshorten links if applicable, otherwise return original url
def unshortenURL(url):
    response = requests.get(url)
    return response.url

#logic for scraping external links
def getWebText(url, min_text_length, unsupported_hosts=[]):
    print(url)

    #check if external content url is explicitly unsupported (e.g. twitter, youtube, etc.)
    isUnsupported = True if any(hostname in url for hostname in unsupported_hosts) else False

    #set extracted text default to blank string
    extracted_text = ''

    if isUnsupported:
        return extracted_text

    fetcher = LinkContentFetcher()
    
    #first try getting html using Haystack component
    try:
        source_html_bytestream = fetcher.run(urls=[url])['streams'][0]
        extracted_text = trafilatura.extract(source_html_bytestream, url=url, deduplicate=True, include_comments=False)
    except Exception as error:
        print("Error:", type(error).__name__, "-", error)
        
    #check output is valid text and long enough
    if extracted_text is not None and len(extracted_text) > min_text_length:
        return extracted_text
    
    #then try get html using basic request instead of Haystack
    try:
        print('Trying basic request with custom headers')
        headers = generateHeaders()
        source_html = requests.get(url, headers=headers).text
        extracted_text = trafilatura.extract(source_html, url=url, deduplicate=True, include_comments=False)
    except Exception as error:
        print("Error:", type(error).__name__, "-", error)
    
    #check output is valid text and long enough
    if extracted_text is not None and len(extracted_text) > min_text_length:
        return extracted_text

    #if can't extract text or extracted text is too short, try google webcache
    try:
        print('Trying webcache')
        source_html_bytestream = fetcher.run(urls=[configs.WEBCACHE_URL + url])['streams'][0]
        extracted_text = trafilatura.extract(source_html_bytestream, url=url, deduplicate=True, include_comments=False)
    except Exception as error:
        print("Error:", type(error).__name__, "-", error)
            
    #check output is valid text and long enough
    if extracted_text is not None and len(extracted_text) > min_text_length:
        return extracted_text
    
    #if that doesn't work, try selenium webdriver browser automation
    driver = None
    try:
        print('Trying browser automation')
        driver = uc.Chrome(headless=True, use_subprocess=False)
        driver.get(url)
        source_html = driver.page_source
        extracted_text = trafilatura.extract(source_html, url=url, deduplicate=True, include_comments=False)
        driver.close()
    except Exception as error:
        print("Error:", type(error).__name__, "-", error)
    finally:
        if driver:
            driver.quit()
    
    #do final check and return text
    return extracted_text if extracted_text and len(extracted_text) > min_text_length else ''

#TWITTER
###################################################################
#API CONFIGS
TW_HOST = 'twitter-api45.p.rapidapi.com'
TW_TWEET_ENDPOINT = 'https://twitter-api45.p.rapidapi.com/tweet.php'
TW_THREAD_ENDPOINT = 'https://twitter-api45.p.rapidapi.com/tweet_thread.php'
TW_TOKEN = utils.read_secrets('RAPID_API_TW_TOKEN')
TW_HEADERS = headers = {
	'X-RapidAPI-Key': TW_TOKEN,
	'X-RapidAPI-Host': TW_HOST
}
TW_DATE_FORMAT = "%a %b %d %H:%M:%S %z %Y"

#PIPELINE CONFIGS

def tweetIDFromURL(url):
    start_substr = '/status/'
    start_idx = url.find(start_substr) + len(start_substr)
    #get substring starting from start_idx
    tid = url[start_idx:]
    #if there is cruff after tweet id, remove it
    if '/' in tid:
        end_idx = tid.find('/')
        tid = tid[:end_idx]
    return tid

def getLinkedTweetText(url):
    #extract tweet id from url
    tid = tweetIDFromURL(unshortenURL(url))
    params = {
        'id': tid,
    }
    #call API
    response = requests.get(TW_TWEET_ENDPOINT, headers=TW_HEADERS, params=params)
    if response.status_code != 200:
        raise Exception(response.status_code, response.text)
    response_json = response.json()
    #assemble main tweet text and quoted tweet text if applicable
    if 'quoted' in response_json.keys() and response_json['quoted']:
        tweet_text = f'{response_json['text']}\n\n"@{response_json['quoted']['author']['screen_name']}: {response_json['quoted']['text']}"'
    else:
        tweet_text = f'{response_json['text']}'
    return tweet_text

#Parse the text of a multi-tweet thread from the same original author
def parseTweetThreadText(tweet_url):
    pass

#Pull latest posts from twitter list's timeline
def getTwitterTimelinePosts(timeline_url):
    pass

#REDDIT
###################################################################

#Reddit API configs
AUTH_URL_REDDIT = 'https://www.reddit.com/api/v1/access_token'
API_URL_REDDIT = 'https://oauth.reddit.com/api/v1/'
LISTINGS_URL_REDDIT = 'https://oauth.reddit.com/r/'
HEADERS_REDDIT = {'User-Agent':'Python:MLnewsletter:v0.1 (by /u/generic_user)'}
CLIENT_ID_REDDIT = 'REPLACE_WITH_REDDIT_CLIENT_ID'
CLIENT_SEC_REDDIT = utils.read_secrets('CLIENT_SEC_REDDIT')
POST_AUTH_REDDIT = {'grant_type':'client_credentials'}

#Reddit pipeline configs
MIN_TEXT_LEN_EXTERNAL_REDDIT = 600 #min characters in scraped external text
MIN_TEXT_LEN_SELF_REDDIT = 200 #min characters for post self text
MIN_TEXT_LEN_TWEET_REDDIT = 50 #min characters for linked tweets

#Reddit - get OAUTH2 token and add to header
client_auth_reddit = requests.auth.HTTPBasicAuth(CLIENT_ID_REDDIT, CLIENT_SEC_REDDIT)
auth_response_reddit = requests.post(AUTH_URL_REDDIT, auth=client_auth_reddit, data=POST_AUTH_REDDIT, headers=HEADERS_REDDIT)
auth_json_reddit = auth_response_reddit.json()
HEADERS_REDDIT['Authorization'] = auth_json_reddit['token_type'] + ' ' + auth_json_reddit['access_token']

#Reddit - pull posts from reddit API
def getSubredditPosts(subreddit, max_posts=10, endpoint='top', region='US') -> list[dict]:
    print(f'SUBREDDIT: {subreddit}')
    if endpoint == 'top':
        params = {'t': 'day', 'g':region, 'limit':max_posts, 'raw_json':1}
    else:
        params = {'g':region, 'limit':max_posts, 'raw_json':1}
    response = requests.get(LISTINGS_URL_REDDIT + subreddit + '/' + endpoint, params=params, headers=HEADERS_REDDIT)
    try:
        output = response.json()['data']['children']
        return output
    except Exception as error:
        print("Error:", type(error).__name__, "-", error)
        print(response)
        raise

#Reddit - define logic for whitelisting certain posts that don't meet min text criteria
def whitelistListingReddit(listing):
    #whitelist posts that have a flair indicating news (short breaking news posts)
    if 'news' in listing['data']['link_flair_text'].lower():
        return True
    #whitelist AI flair posts
    if 'AI' in listing['data']['link_flair_text']:
        return True
    return False

#Reddit - find and extract first link from selftext if it exists
def extractSelftextLinkReddit(text):
    pattern = r'\[(.*?)\]\((.*?)\)'
    m = re.search(pattern, text)
    link = m.group(2) if m is not None else None
    return link

#Reddit - parse out fields from returned json and reformat into clean data structure
def parseFeedReddit(topic_id, feed_id, min_timestamp=0, max_posts=10, endpoint='top', region='US', printstats=False) -> list[dict]:
    subreddit = db.getFeedURL(feed_id)
    raw_listings_json = getSubredditPosts(subreddit, max_posts, endpoint, region)
    posts = []

    #logging for tracking success of processing
    total = 0
    has_text_count = 0
    has_external_link_count = 0
    external_success_count = 0
    total_success_count = 0

    #repackage key fields from each post
    for listing in raw_listings_json:

        #add full URL to post permalink
        post_link = utils.standardizeURL('https://www.reddit.com' + listing['data']['permalink'])

        #check if post permalink is duplicate
        if isDuplicateLink(post_link) or any(post['post_link'] == post_link for post in posts):
            print('Skipped duplicate (post link)')
            continue

        total += 1

        #check for link or post self text
        if 'url_overridden_by_dest' in listing['data'] or listing['data']['selftext'] is not None:
            #skip if post older than cutoff date
            if listing['data']['created_utc'] < min_timestamp:
                continue

            #skip if pinned post
            if listing['data']['stickied'] == True:
                continue

            has_text_count += 1

            #set link to provided link if available
            external_content_link = utils.standardizeURL(listing['data']['url_overridden_by_dest']) if 'url_overridden_by_dest' in listing['data'] and listing['data']['url_overridden_by_dest'] is not None else None
            
            #if no explicit external content link, check self text for link
            if external_content_link is None and listing['data']['selftext'] is not None:
                external_content_link = extractSelftextLinkReddit(listing['data']['selftext'])

            #check if link is a reddit domain
            reddit_hostnames = configs.REDDIT_HOSTNAMES
            if external_content_link:
                isRedditLink = True if listing['data']['is_reddit_media_domain'] == True or any(hostname in external_content_link for hostname in reddit_hostnames) else False
            else:
                isRedditLink = False

            #CASE 1: HAS EXTERNAL LINK
            if external_content_link is not None and isRedditLink == False:
                #check if link is valid
                isValid = True if 'http' in external_content_link else False
                #skip if link is not valid
                if isValid == False:
                    continue

                #check if duplicate external link
                if isDuplicateLink(external_content_link) or any(post['external_link'] == external_content_link for post in posts):
                    print('Skipped duplicate (external link)')
                    continue

                #check if link is twitter domain
                twitter_hostnames = configs.TWITTER_HOSTNAMES
                isTwitter = True if any(hostname in external_content_link for hostname in twitter_hostnames) else False

                has_external_link_count += 1

                #CASE 1A: TWITTER LINK
                if isTwitter:
                    external_scraped_text = getLinkedTweetText(external_content_link)
                    #skip if external scraped text is empty
                    if external_scraped_text is None or len(external_scraped_text) < MIN_TEXT_LEN_TWEET_REDDIT:
                        continue
                #CASE 1B: OTHER WEBSITE LINK
                else:
                    #scrape using general web scraper
                    external_scraped_text = getWebText(external_content_link, min_text_length=MIN_TEXT_LEN_EXTERNAL_REDDIT, unsupported_hosts=configs.WEB_SCRAPE_UNSUPPORTED_HOSTS)
                    #skip if external scraped text shorter than min characters
                    if len(external_scraped_text) < MIN_TEXT_LEN_EXTERNAL_REDDIT:
                        continue

                #final check for duplicate post based on extracted text
                if isDuplicateText(title=listing['data']['title'], external_text=external_scraped_text):
                    print('Skipped duplicate (title/external-text)')
                    continue

                if any(post['post_title'] == listing['data']['title'] for post in posts) and listing['data']['title'] is not None and listing['data']['title'] != '':
                    print('Skipped duplicate (title/text)')
                    continue

                if any(post['external_parsed_text'] == external_scraped_text for post in posts) and external_scraped_text is not None and external_scraped_text != '':
                    print('Skipped duplicate (title/text)')
                    continue

                external_success_count += 1
                total_success_count += 1

            #CASE 2: NO EXTERNAL LINK, ONLY SELF TEXT
            else:
                #set link and scraped content to to none
                external_content_link = None
                external_scraped_text = None

                #skip if self text shorter than min characters and does not meet any post whitelist criteria
                if len(listing['data']['selftext']) < MIN_TEXT_LEN_SELF_REDDIT and whitelistListingReddit(listing) == False:
                    continue

                #final check for duplicate post based on extracted text
                if isDuplicateText(title=listing['data']['title'], post_text=listing['data']['selftext']):
                    print('Skipped duplicate (title/post-text)')
                    continue

                if any(post['post_title'] == listing['data']['title'] for post in posts) and listing['data']['title'] is not None and listing['data']['title'] != '':
                    print('Skipped duplicate (title/text)')
                    continue

                if any(post['post_text'] == listing['data']['selftext'] for post in posts) and listing['data']['selftext'] is not None and listing['data']['selftext'] != '':
                    print('Skipped duplicate (title/text)')
                    continue

                total_success_count += 1
            
            #check if fields exist
            image_url = [url['source']['url'] for url in listing['data']['preview']['images']] if 'preview' in listing['data'] else None

            #process link flair
            post_tags = [listing['data']['link_flair_text']] if listing['data']['link_flair_text'] is not None else None

            #package extracted post
            parsed_post = {
                #No post_id, id is created by DB
                'feed_id': feed_id,
                'story_id': None,
                'topic_id': topic_id,
                #no created_at, DB defaults to current time
                #no updated_at, DB defaults to current time
                'content_unique_id': listing['data']['name'],
                'post_publish_time': datetime.fromtimestamp(listing['data']['created_utc']),
                'post_link': post_link,
                'post_title': listing['data']['title'],
                'post_tags': json.dumps(post_tags),
                'post_description': None,
                'post_text': listing['data']['selftext'],
                'image_urls': json.dumps(image_url),
                'external_link': external_content_link,
                'external_parsed_text': external_scraped_text,
                'views_score': None,
                'likes_score': listing['data']['score'],
                'comments_score': None,
                'category_ml': None,
                'summary_ml': None
            }

            posts.append(parsed_post)

    #print summary stats
    if printstats:
        print(f'Total posts pulled: {total} \nPosts with text or link: {has_text_count} \nPosts processed successfully: {total_success_count} \n\nPosts with external link: {has_external_link_count} \nExternal links processed successfully: {external_success_count}')
    return posts

#RSS FEED
##################################################################
MIN_TEXT_LEN_EXTERNAL_RSS = 600
MIN_TEXT_LEN_SELF_RSS = 600

#pull posts from RSS feed 
def getRSSPosts(feed_url):
    raw_feed = feedparser.parse(feed_url)
    return raw_feed

def parseFeedRSS(topic_id, feed_id, min_timestamp=0) -> list[dict]:
    feed_url = db.getFeedURL(feed_id)
    raw_feed = getRSSPosts(feed_url)
    posts = []
    
    for entry in raw_feed.entries:
        #check if newer than specified timestamp (raw UNIX timestamp)
        publish_time = datetime.fromtimestamp(time.mktime(entry.published_parsed)) #convert to datetime format for DB
        if time.mktime(entry.published_parsed)< min_timestamp:
            continue
        
        post_link = utils.standardizeURL(entry.link) if 'link' in entry else None
        #check if already exists in DB, skip if so
        if post_link is not None:
            if isDuplicateLink(entry.link) or any(post['post_link'] == entry.link for post in posts):
                print('Skipped duplicate (link)')
                continue

        #check if there is self text included
        if 'content' in entry:
            #check if self content is html, if so, parse out text (REFACTOR LOGIC TO CHECK NUM TOKENS, IF TOKENS EXCEED MAX THEN PARSE HTML, OTHERWISE LEAVE IT)
            #if 'html' in entry.content[0]['type']:
                #post_text = trafilatura.extract(entry.content[0]['value'], deduplicate=True, include_comments=False)
            #else:
                #post_text = entry.content[0]['value']
            post_text = entry.content[0]['value']
        else:
            post_text = None
            
        #if self text is less than minimum or no self text, scrape external link
        if len(post_text if post_text is not None else '') < MIN_TEXT_LEN_SELF_RSS:
            unsupported_hosts = configs.WEB_SCRAPE_UNSUPPORTED_HOSTS
            external_parsed_text = getWebText(entry.link, min_text_length=MIN_TEXT_LEN_EXTERNAL_RSS, unsupported_hosts=unsupported_hosts)
            #skip if scraped text also does not have extractable content
            if external_parsed_text == '':
                continue
        else:
            external_parsed_text = None

        #check for existence of fields in feed
        content_unique_id = entry.id if 'id' in entry else None
        headline = entry.title if 'title' in entry else None
        description = entry.description if 'description' in entry else None

        #check for duplicate post based on extracted text
        if isDuplicateText(title=headline, post_text=post_text, external_text=external_parsed_text):
            print('Skipped duplicate (title/text)')
            continue
        
        if any(post['post_title'] == headline for post in posts) and headline is not None and headline != '':
            print('Skipped duplicate (title/text)')
            continue

        if any(post['post_text'] == post_text for post in posts) and post_text is not None and post_text != '':
            print('Skipped duplicate (title/text)')
            continue

        if any(post['external_parsed_text'] == external_parsed_text for post in posts) and external_parsed_text is not None and external_parsed_text != '':
            print('Skipped duplicate (title/text)')
            continue

        #logic for getting image url if it exists
        if entry.enclosures == []:
            if 'media_thumbnail' in entry:
                media_type = 'image/jpeg'
                media_url = [utils.standardizeURL(url['url']) for url in entry.media_thumbnail]
            else:
                media_type = None
                media_url = None
        else:
            media_type = entry.enclosures[0].type
            media_url = [utils.standardizeURL(url.href) for url in entry.enclosures]

        #save extracted post
        posts.append({
        #No post_id, id is created by DB
        'feed_id': feed_id,
        'story_id': None,
        'topic_id': topic_id,
        #no created_at, DB defaults to current time
        #no updated_at, DB defaults to current time
        'content_unique_id': content_unique_id,
        'post_publish_time': publish_time,
        'post_link': post_link,
        'post_title': headline,
        'post_tags': None,
        'post_description': description,
        'post_text': post_text,
        'image_urls': json.dumps(media_url),
        'external_link': post_link,
        'external_parsed_text': external_parsed_text,
        'views_score': None,
        'likes_score': None,
        'comments_score': None,
        'category_ml': None,
        'summary_ml': None
        })

    return posts
