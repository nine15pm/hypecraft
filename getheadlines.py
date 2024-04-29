import os
import json
import feedparser
import requests
import requests.auth
import time

#REDDIT TEST
###################################################################

#Read secrets json
def read_secrets():
    filename = os.path.join('secrets.json')
    try:
        with open(filename, mode='r') as f:
            return json.loads(f.read())
    except FileNotFoundError:
        return {}

#Reddit API configs
AUTH_URL_REDDIT = 'https://www.reddit.com/api/v1/access_token'
API_URL_REDDIT = 'https://oauth.reddit.com/api/v1/'
LISTINGS_URL_REDDIT = 'https://oauth.reddit.com/r/'
HEADERS_REDDIT = {'User-Agent':'Python:MLnewsletter:v0.1 (by /u/generic_user)'}
CLIENT_ID_REDDIT = 'REPLACE_WITH_REDDIT_CLIENT_ID'
CLIENT_SEC_REDDIT = read_secrets()['CLIENT_SEC_REDDIT']
POST_AUTH_REDDIT = {'grant_type':'client_credentials'}

#Reddit - get OAUTH2 token and add to header
client_auth_reddit = requests.auth.HTTPBasicAuth(CLIENT_ID_REDDIT, CLIENT_SEC_REDDIT)
auth_response_reddit = requests.post(AUTH_URL_REDDIT, auth=client_auth_reddit, data=POST_AUTH_REDDIT, headers=HEADERS_REDDIT)
auth_json_reddit = auth_response_reddit.json()
HEADERS_REDDIT['Authorization'] = auth_json_reddit['token_type'] + ' ' + auth_json_reddit['access_token']

#Reddit - parse out fields from returned json and reformat into clean data structure
def parseRedditListings(raw_listings_json, newer_than_datetime=0):
  posts = []

  #filter out the pinned posts
  filtered_listings = [listing for listing in raw_listings_json if listing['data']['stickied'] == False]

  #repackage key fields from each post
  for listing in filtered_listings:

    #filtering conditions, skip post if any of these are met
    if listing['data']['created_utc'] < newer_than_datetime:  #check if it's newer than specified timestamp (raw UNIX timestamp)
       continue
    
    #check if fields exist
    image_url = listing['data']['preview']['images'][0]['source']['url'] if 'preview' in listing['data'] else None

    #add full URL to post permalink
    post_link = 'https://www.reddit.com' + listing['data']['permalink']

    #save extracted post
    posts.append({
      'post_ID': listing['data']['name'],
      'publish_time': listing['data']['created_utc'],
      'post_link': post_link,
      'headline': listing['data']['title'],
      'post_text': listing['data']['selftext'],
      'preview_img_url': image_url,
      'external_content_link': listing['data']['url'],
      'vote_score': listing['data']['score'],
      'num_comments': listing['data']['num_comments'],
      'subreddit': listing['data']['subreddit']
    })

  return posts

#Reddit - get hot posts from subreddit
def getRedditPosts(subreddit, max_posts, filter='hot', region='US', newer_than_datetime=0):
  params = {'g':region, 'limit':max_posts, 'raw_json':1}
  response = requests.get(LISTINGS_URL_REDDIT + subreddit + '/' + filter, params=params, headers=HEADERS_REDDIT)
  print(response.json()['data']['children'])
  return parseRedditListings(response.json()['data']['children'], newer_than_datetime)

#SUBSTACK TEST
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