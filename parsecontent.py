import feedparser
import requests
import requests.auth
import utils
import time
import urllib.parse
import ua_generator
from selenium import webdriver
import undetected_chromedriver as uc
import trafilatura

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

#Reddit parsing configs
MIN_TEXT_LEN_EXTERNAL_REDDIT = 350 #min characters in scraped external text
MIN_TEXT_LEN_SELF_REDDIT = 200 #min characters for post self text

#Reddit - get OAUTH2 token and add to header
client_auth_reddit = requests.auth.HTTPBasicAuth(CLIENT_ID_REDDIT, CLIENT_SEC_REDDIT)
auth_response_reddit = requests.post(AUTH_URL_REDDIT, auth=client_auth_reddit, data=POST_AUTH_REDDIT, headers=HEADERS_REDDIT)
auth_json_reddit = auth_response_reddit.json()
HEADERS_REDDIT['Authorization'] = auth_json_reddit['token_type'] + ' ' + auth_json_reddit['access_token']

#Reddit - parse out fields from returned json and reformat into clean data structure
def parseRedditListings(raw_listings_json, newer_than_datetime=0):
  posts = []

  #logging for tracking success of processing
  total = len(raw_listings_json)
  has_text_count = 0
  has_external_link_count = 0
  external_success_count = 0
  total_success_count = 0

  #repackage key fields from each post
  for listing in raw_listings_json:

    #initial filter to only posts with external links or sufficient self-text
    if listing['data']['url'] is not None or listing['data']['selftext'] is not None:
      has_text_count += 1

      #filter out posts older than cutoff date
      if listing['data']['created_utc'] < newer_than_datetime:
        continue

      #filter out pinned posts
      if listing['data']['stickied'] == True:
        continue

      #scrape external content text if applicable
      if listing['data']['url'] is not None:
        has_external_link_count += 1
        external_scraped_text = getWebText(listing['data']['url'])

        #filter out posts with external scraped text shorter than min characters
        if len(external_scraped_text) < MIN_TEXT_LEN_EXTERNAL_REDDIT:
          continue

        external_success_count += 1
        total_success_count += 1

      #if no external link, then check self text
      else:
        #filter out posts with self text shorter than min characters
        if len(listing['data']['selftext']) < MIN_TEXT_LEN_SELF_REDDIT:
          continue

        total_success_count += 1
      
      #check if fields exist
      image_url = listing['data']['preview']['images'][0]['source']['url'] if 'preview' in listing['data'] else None

      #add full URL to post permalink
      post_link = 'https://www.reddit.com' + listing['data']['permalink']

      #package extracted post
      posts.append({
        'post_ID': listing['data']['name'],
        'publish_time': listing['data']['created_utc'],
        'post_link': post_link,
        'post_flair': listing['data']['link_flair_text'],
        'headline': listing['data']['title'],
        'post_text': listing['data']['selftext'],
        'preview_img_url': image_url,
        'external_content_link': listing['data']['url'],
        'external_scraped_text': external_scraped_text,
        'vote_score': listing['data']['score'],
        'num_comments': listing['data']['num_comments'],
        'subreddit': listing['data']['subreddit']
      })

  #print summary stats
  print(f'''
        Total posts pulled: {total} \n
        Posts with text or link: {has_text_count} \n
        Posts processed successfully: {total_success_count} \n\n

        Posts with external link: {has_external_link_count} \n
        External links processed successfully: {external_success_count}
        ''')
  return posts

#Reddit - get hot posts from subreddit
def getRedditPosts(subreddit, max_posts, filter='hot', region='US', newer_than_datetime=0):
  params = {'g':region, 'limit':max_posts, 'raw_json':1}
  response = requests.get(LISTINGS_URL_REDDIT + subreddit + '/' + filter, params=params, headers=HEADERS_REDDIT)
  return parseRedditListings(response.json()['data']['children'], newer_than_datetime)

#Reddit - scrape content from external links

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
def getWebText(url, min_text_length):
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

  #check if external content url is twitter
  isTwitter = True if urllib.parse.urlparse(url).hostname == 'x.com' or urllib.parse.urlparse(url).hostname == 'www.x.com' else False

  if isTwitter:
    return ''
  else:
    #first try getting html using basic request
    source_html = requests.get(url, headers=headers).text
    print(source_html)
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
      print(source_html)
      extracted_text = trafilatura.extract(source_html, url=url, deduplicate=True, include_comments=False)
      extracted_text = extracted_text if extracted_text is not None and len(extracted_text) > min_text_length else '' #check output is valid text and long enough
      return extracted_text

#SUBSTACK
###################################################################
#Configs
SUBSTACK_APPEND_URL = '.substack.com/feed'

#Substack - parse out content from RSS feed and reformat into clean data structure
def parseSubstackFeed(raw_feed, newer_than_datetime=0):
  posts = []
  substack_name = raw_feed.feed.title

  for entry in raw_feed.entries:
    #check if newer than specified timestamp (raw UNIX timestamp)
    publish_time = time.mktime(entry.published_parsed) #convert to UNIX timestamp

    if publish_time < newer_than_datetime:
      continue

    #check for existence of fields in feed
    post_ID = entry.id if 'id' in entry else None
    post_link = entry.link if 'link' in entry else None
    headline = entry.title if 'title' in entry else None
    description = entry.description if 'description' in entry else None
    post_content = entry.content[0]['value'] if 'content' in entry else None
    media_type = entry.enclosures[0].type if 'enclosures' in entry else None
    media_url = entry.enclosures[0].href if 'enclosures' in entry else None

    #save extracted post
    posts.append({
      'post_ID': entry.get('id', None),
      'publish_time': publish_time,
      'post_link': post_link,
      'headline': headline,
      'description': description,
      'post_content': post_content,
      'media_type': media_type,
      'media_url': media_url,
      'substack_name': substack_name
    })

  return posts

#Substack - get posts from blog RSS feed
def getSubstackPosts(substack_name, newer_than_datetime=0):
  feed_url = 'https://' + substack_name + SUBSTACK_APPEND_URL
  raw_feed = feedparser.parse(feed_url)
  return parseSubstackFeed(raw_feed, newer_than_datetime)