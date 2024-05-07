import feedparser
import requests
import requests.auth
import utils
import configs
import time
import ua_generator
import undetected_chromedriver as uc
import trafilatura

#GENERAL TEXT EXTRACTOR FOR EXTERNAL LINKS
###################################################################

#Custom class to fix error with undetected_chromedriver library (used for backup browser automation scrape method)
class Chrome(uc.Chrome):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def quit(self):
        try:
            super().quit()
        except OSError:
            pass
        
#logic for scraping external links
def getWebText(url, min_text_length, unsupported_hosts=[]):
    print(url)
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

    #check if external content url is explicitly unsupported (e.g. twitter, youtube, etc.)
    isUnsupported = True if any(hostname in url for hostname in unsupported_hosts) else False

    if isUnsupported:
        return ''
    else:
        #first try getting html using basic request
        source_html = requests.get(url, headers=headers).text
        extracted_text = trafilatura.extract(source_html, url=url, deduplicate=True, include_comments=False)
        #check output is valid text and long enough
        if extracted_text is not None and len(extracted_text) > min_text_length:
            return extracted_text
        else:
            #if can't extract text using basic request or extracted text is too short (likely garbage), try selenium webdriver browser automation
            driver = Chrome(headless=True, use_subprocess=True)
            driver.get(url)
            source_html = driver.page_source
            driver.close()
            extracted_text = trafilatura.extract(source_html, url=url, deduplicate=True, include_comments=False)
            extracted_text = extracted_text if extracted_text is not None and len(extracted_text) > min_text_length else '' #check output is valid text and long enough
            return extracted_text

#REDDIT
###################################################################

#Reddit API configs
AUTH_URL_REDDIT = 'https://www.reddit.com/api/v1/access_token'
API_URL_REDDIT = 'https://oauth.reddit.com/api/v1/'
LISTINGS_URL_REDDIT = 'https://oauth.reddit.com/r/'
HEADERS_REDDIT = {'User-Agent':'Python:MLnewsletter:v0.1 (by /u/generic_user)'}
CLIENT_ID_REDDIT = 'REPLACE_WITH_REDDIT_CLIENT_ID'
CLIENT_SEC_REDDIT = utils.read_secrets()['CLIENT_SEC_REDDIT']
POST_AUTH_REDDIT = {'grant_type':'client_credentials'}

#Reddit pipeline configs
MIN_TEXT_LEN_EXTERNAL_REDDIT = 450 #min characters in scraped external text
MIN_TEXT_LEN_SELF_REDDIT = 200 #min characters for post self text

#Reddit - get OAUTH2 token and add to header
client_auth_reddit = requests.auth.HTTPBasicAuth(CLIENT_ID_REDDIT, CLIENT_SEC_REDDIT)
auth_response_reddit = requests.post(AUTH_URL_REDDIT, auth=client_auth_reddit, data=POST_AUTH_REDDIT, headers=HEADERS_REDDIT)
auth_json_reddit = auth_response_reddit.json()
HEADERS_REDDIT['Authorization'] = auth_json_reddit['token_type'] + ' ' + auth_json_reddit['access_token']

#Reddit - pull posts from reddit API
def getRedditPosts(subreddit, max_posts, endpoint='top', region='US') -> list[dict]:
    if endpoint == 'top':
        params = {'t': 'day', 'g':region, 'limit':max_posts, 'raw_json':1}
    else:
        params = {'g':region, 'limit':max_posts, 'raw_json':1}
    response = requests.get(LISTINGS_URL_REDDIT + subreddit + '/' + endpoint, params=params, headers=HEADERS_REDDIT)
    return response.json()['data']['children']

#Reddit - parse out fields from returned json and reformat into clean data structure
def parseRedditListings(raw_listings_json, newer_than_datetime=0, printstats=False) -> list[dict]:
    posts = []

    #logging for tracking success of processing
    total = len(raw_listings_json)
    has_text_count = 0
    has_external_link_count = 0
    external_success_count = 0
    total_success_count = 0

    #repackage key fields from each post
    for listing in raw_listings_json:

        #check for link or post self text
        if 'url_overridden_by_dest' in listing['data'] or listing['data']['selftext'] is not None:
            #skip if post older than cutoff date
            if listing['data']['created_utc'] < newer_than_datetime:
                continue

            #skip if pinned post
            if listing['data']['stickied'] == True:
                continue

            has_text_count += 1

            #CASE 1: HAS EXTERNAL LINK
            if 'url_overridden_by_dest' in listing['data'] and listing['data']['url_overridden_by_dest'] is not None:
                #set link to provided link
                external_content_link = listing['data']['url_overridden_by_dest']
                
                #check if link is a reddit domain
                reddit_hostnames = configs.REDDIT_HOSTNAMES
                isRedditLink = True if listing['data']['is_reddit_media_domain'] == True or any(hostname in listing['data']['url_overridden_by_dest'] for hostname in reddit_hostnames) else False

                #check if link is valid
                isValid = True if 'http' in listing['data']['url_overridden_by_dest'] else False

                #skip if link is not external or not valid
                if isRedditLink == True or isValid == False:
                    continue

                has_external_link_count += 1

                #scrape the text
                #define unsupported hosts to ignore
                unsupported_hosts = configs.WEB_SCRAPE_UNSUPPORTED_HOSTS
                external_scraped_text = getWebText(listing['data']['url'], min_text_length=MIN_TEXT_LEN_EXTERNAL_REDDIT, unsupported_hosts=unsupported_hosts)

                #skip if external scraped text shorter than min characters
                if len(external_scraped_text) < MIN_TEXT_LEN_EXTERNAL_REDDIT:
                    continue

                external_success_count += 1
                total_success_count += 1

            #CASE 2: NO EXTERNAL LINK, ONLY SELF TEXT
            else:
                #set link and scraped content to to none
                external_content_link = None
                external_scraped_text = None

                #skip if self text shorter than min characters
                if len(listing['data']['selftext']) < MIN_TEXT_LEN_SELF_REDDIT:
                    continue

                total_success_count += 1
            
            #check if fields exist
            image_url = listing['data']['preview']['images'][0]['source']['url'] if 'preview' in listing['data'] else None

            #add full URL to post permalink
            post_link = 'https://www.reddit.com' + listing['data']['permalink']

            #package extracted post
            posts.append({
                'post_id': listing['data']['name'],
                'publish_time': listing['data']['created_utc'],
                'post_link': post_link,
                'post_tags': listing['data']['link_flair_text'],
                'headline': listing['data']['title'],
                'description': None,
                'post_text': listing['data']['selftext'],
                'preview_img_url': image_url,
                'external_content_link': external_content_link,
                'external_scraped_text': external_scraped_text,
                'vote_score': listing['data']['score'],
                'num_comments': listing['data']['num_comments'],
                'subreddit': listing['data']['subreddit'],
                'source': 'reddit'
            })

    #print summary stats
    if printstats:
        print(f'Total posts pulled: {total} \nPosts with text or link: {has_text_count} \nPosts processed successfully: {total_success_count} \n\nPosts with external link: {has_external_link_count} \nExternal links processed successfully: {external_success_count}')
    return posts

#RSS FEED
##################################################################
MIN_TEXT_LEN_EXTERNAL_RSS = 450
MIN_TEXT_LEN_SELF_RSS = 450
RSS_URL = 'https://semianalysis.substack.com/feed'
# https://feeds.bbci.co.uk/sport/formula1/rss.xml, https://feeds.feedburner.com/F1fanatic, https://www.autosport.com/rss/f1/news
# https://semianalysis.substack.com/feed

#pull posts from RSS feed
def getRSSPosts(feed_url):
    raw_feed = feedparser.parse(feed_url)
    return raw_feed

def parseRSSFeed(raw_feed, newer_than_datetime=0) -> list[dict]:
    posts = []
    
    for entry in raw_feed.entries:

        #check if newer than specified timestamp (raw UNIX timestamp)
        publish_time = time.mktime(entry.published_parsed) #convert to UNIX timestamp
        if publish_time < newer_than_datetime:
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
            external_scraped_text = getWebText(entry.link, min_text_length=MIN_TEXT_LEN_EXTERNAL_RSS, unsupported_hosts=unsupported_hosts)
            #skip if scraped text also does not have extractable content
            if external_scraped_text == '':
                continue
        else:
            external_scraped_text = None

        #check for existence of fields in feed
        post_id = entry.id if 'id' in entry else None
        post_link = entry.link if 'link' in entry else None
        headline = entry.title if 'title' in entry else None
        description = entry.description if 'description' in entry else None

        #logic for getting image url if it exists
        if entry.enclosures == []:
            if 'media_thumbnail' in entry:
                media_type = 'image/jpeg'
                media_url = entry.media_thumbnail[0]['url']
            else:
                media_type = None
                media_url = None
        else:
            media_type = entry.enclosures[0].type
            media_url = entry.enclosures[0].href

        #save extracted post
        posts.append({
        'post_id': post_id,
        'publish_time': publish_time,
        'post_link': post_link,
        'post_tags': None,
        'headline': headline,
        'description': description,
        'post_text': post_text,
        'preview_img_url': media_url,
        'external_content_link': post_link,
        'external_scraped_text': external_scraped_text,
        'vote_score': None,
        'num_comments': None,
        'subreddit': None,
        'source': 'RSS'
        })

    return posts