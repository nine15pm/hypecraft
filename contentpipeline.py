import utils
import db
import sourcer
import editor
import configs
import time
from pytz import timezone
from datetime import datetime, time, timedelta

#CONFIGS
##############################################################################################
DATETIME_TODAY_START = datetime.combine(datetime.today(), time.min).astimezone(timezone(configs.LOCAL_TZ))
MIN_DATETIME_DEFAULT = datetime.fromtimestamp(0)
MAX_DATETIME_DEFAULT = datetime.fromtimestamp(datetime.now().timestamp() + 1e9)

#PIPELINE STEPS
##############################################################################################

#get posts, scrape/process external links, save to DB
def pullPosts(topic_id, max_posts_reddit, min_timestamp):
    #get topic feeds
    feeds = db.getFeedsForTopic(topic_id)
    parsed_posts = []

    #pull and process posts for each feed
    for feed in feeds:
        if feed['feed_type'] == 'rss':
            parsed_posts = parsed_posts + sourcer.parseFeedRSS(topic_id=topic_id, feed_id=feed['feed_id'], min_timestamp=min_timestamp)
        elif feed['feed_type'] == 'subreddit':
            parsed_posts = parsed_posts + sourcer.parseFeedReddit(topic_id=topic_id, feed_id=feed['feed_id'], min_timestamp=min_timestamp, max_posts=max_posts_reddit, printstats=True)

    #save to DB
    db.createPosts(parsed_posts)
    print("Posts pulled and saved to DB")

#load posts, classify category using model, update in DB
def categorizePosts(topic_id, min_datetime, max_datetime=MAX_DATETIME_DEFAULT):
    posts = db.getPostsForCategorize(topic_id, min_datetime=min_datetime, max_datetime=max_datetime)
    feed_ids = [post['feed_id'] for post in posts]
    feeds = db.getFeedsForPosts(feed_ids)
    posts_update = []

    for idx, post in enumerate(posts):
        feed = [feed for feed in feeds if feed['feed_id'] == post['feed_id']][0]
        category = editor.classifyPost(post=post, feed=feed)
        posts_update.append({
            'post_id': post['post_id'],
            'category_ml': category
        })
        print(f'CATEGORIZE POSTS: {idx+1} of {len(posts)} processed')
    
    db.updatePosts(posts_update)
    print(f'Post categories updated in DB')

#load news posts, generate summary, update in DB
def summarizeNewsPosts(topic_id, min_datetime, max_datetime=MAX_DATETIME_DEFAULT):
    posts = db.getPostsForNewsSummary(topic_id, min_datetime=min_datetime, max_datetime=max_datetime)
    feed_ids = [post['feed_id'] for post in posts]
    feeds = db.getFeedsForPosts(feed_ids)
    posts_update = []

    for idx, post in enumerate(posts):
        feed = [feed for feed in feeds if feed['feed_id'] == post['feed_id']][0]
        summary = editor.generateNewsPostSummary(post=post, feed=feed)
        posts_update.append({
            'post_id': post['post_id'],
            'summary_ml': summary
        })
        print(f'SUMMARIZE NEWS POST: {idx+1} of {len(posts)} processed')
    
    db.updatePosts(posts_update)
    print(f'News post summaries updated in DB')

#load news posts, group into stories, save stories to DB
def mapStories(topic_id, min_datetime):
    topic_name = db.getTopics(filters={'topic_id': topic_id})[0]['topic_name']
    news_posts = db.getPostsForNewsStoryMapping(topic_id, min_datetime=min_datetime)
    mapping = editor.mapNewsPostsToStories(news_posts, topic_name=topic_name)
    stories = []
    #parse and format into story objects for DB
    for story in mapping:
        stories.append({
            'topic_id': topic_id,
            'posts': story['pid']
        })
    db.createStories(stories)
    #fill in story_id column in Post table
    stories = db.getStoriesForTopic(topic_id, min_datetime=min_datetime)
    for story in stories:
        posts = []
        for post_id in story['posts']:
            posts.append({
                'post_id': post_id,
                'story_id': story['story_id']
            })
        db.updatePosts(posts)
    print('Stories mapped and saved to DB')

#load stories, generate story summary, update in DB
def summarizeStories(topic_id, min_datetime, max_datetime=MAX_DATETIME_DEFAULT):
    topic_name = db.getTopics(filters={'topic_id': topic_id})[0]['topic_name']
    stories = db.getStoriesForTopic(topic_id, min_datetime=min_datetime, max_datetime=max_datetime)
    story_updates = []

    for idx, story in enumerate(stories):
        try:
            posts = db.getPostsForStorySummary(story['posts'])
            summary, posts_summarized = editor.generateStorySummary(posts, topic_name)
            headline = editor.generateHeadlineFromSummary(summary)
            story_updates.append({
                'story_id': story['story_id'],
                'posts_summarized': posts_summarized,
                'summary_ml': summary,
                'headline_ml': headline
            })
            print(f'SUMMARIZE STORY: {idx+1} of {len(stories)} processed')
        except Exception as error:
            print(f'Error summarizing story ID [{story['story_id']}]:', type(error).__name__, "-", error)
            print(f'Linked posts: [{story['posts']}]')
            raise

    db.updateStories(story_updates)
    print(f'Story summaries updated in DB')

def rankStories(topic_id, min_datetime, max_datetime=MAX_DATETIME_DEFAULT):
    topic_name = db.getTopics(filters={'topic_id': topic_id})[0]['topic_name']
    stories = db.getStoriesForTopic(topic_id, min_datetime=min_datetime, max_datetime=max_datetime)
    stories_scores = editor.scoreNewsStories(stories, topic_name)
    story_updates = []

    for story in stories_scores:
        story_updates.append({
            'story_id': story['hid'],
            'daily_i_score_ml': story['i_score']
        })

    db.updateStories(story_updates)
    print(f'Stories scored and i_scores updated in DB')

#load stories, generate topic summary
def summarizeTopic(topic_id, max_stories, min_datetime, max_datetime=MAX_DATETIME_DEFAULT):
    topic_name = db.getTopics(filters={'topic_id': topic_id})[0]['topic_name']
    stories = db.getStoriesForTopic(topic_id, min_datetime=min_datetime, max_datetime=max_datetime)
    if len(stories) > max_stories:
        stories_ranked = sorted(stories, key=lambda story: story['daily_i_score_ml'], reverse=True)
        stories = stories_ranked[0:max_stories-1]
    topic_highlights = [{
        'topic_id': topic_id,
        'summary_ml': editor.generateTopicSummary(stories, topic_name)
    }]

    db.createTopicHighlight(topic_highlights)
    print(f'Topic summary saved to DB')

#CSV dump for checking story mapping
def storyMappingToCSV(topic_id, min_datetime, max_datetime=MAX_DATETIME_DEFAULT):
    topic_name = db.getTopics(filters={'topic_id': topic_id})[0]['topic_name']
    mapping = []
    stories = db.getStoriesForTopic(topic_id, min_datetime=min_datetime, max_datetime=max_datetime)
    for story in stories:
        posts = db.getPostsForStorySummary(story['posts'])
        headlines_str = ''
        post_id_str = ''
        post_link_str = ''
        for i, post in enumerate(posts):
            post_id_str = post_id_str + f'{i}: "{post['post_id']}"\n'
            post_link_str = post_link_str + f'{i}: "{post['post_link']}"\n'
            headlines_str = headlines_str + f'{i}: "{post['post_title']}"\n'
        mapping.append({
            'story_id': story['story_id'],
            'post_ids': post_id_str,
            'post_links': post_link_str,
            'post_headlines': headlines_str
        })
    end_daterange = f'to{max_datetime.strftime('%m-%d')}' if max_datetime != MAX_DATETIME_DEFAULT else ''
    utils.JSONtoCSV(mapping, 'data/story_mapping_' + topic_name + '_' + min_datetime.strftime('%m-%d') + end_daterange + '.csv')
    print('Story mapping output to CSV')

#CSV dump for QA story summary content
def storyQAToCSV(topic_id, min_datetime, max_datetime=MAX_DATETIME_DEFAULT):
    topic_name = db.getTopics(filters={'topic_id': topic_id})[0]['topic_name']
    story_summary_qa = []
    stories = db.getStoriesForTopic(topic_id, min_datetime=min_datetime, max_datetime=max_datetime)
    for story in stories:
        posts = db.getPostsForStoryQA(story['posts_summarized'])
        QA_json = {
            'story_id': story['story_id'],
            'daily_i_score': story['daily_i_score_ml'],
            'story_headline': story['headline_ml'],
            'story_summary': story['summary_ml']
        }
        for i, post in enumerate(posts):
            QA_json[f'post_{i}'] = f'[POST TITLE] {post['post_title']} \n\n\
            [ML SUMMARY] {post['summary_ml']} \n\n\
            [POST LINK] {post['post_link']} \n\
            [POST SELF TEXT] {post['post_text']} \n\n\
            [EXTERNAL LINK] {post['external_link']} \n\
            [EXTERNAL TEXT] {post['external_parsed_text']}'
        story_summary_qa.append(QA_json)
    end_daterange = f'to{max_datetime.strftime('%m-%d')}' if max_datetime != MAX_DATETIME_DEFAULT else ''
    utils.JSONtoCSV(story_summary_qa, 'data/story_summary_QA_' + topic_name + '_' + min_datetime.strftime('%m-%d') + end_daterange + '.csv')
    print('Story QA output to CSV')

#CSV dumps for overall data
def dailyPipelineToCSV(min_datetime, max_datetime=MAX_DATETIME_DEFAULT):
    topic_name = db.getTopics(filters={'topic_id': topic_id})[0]['topic_name']
    #general data dump
    posts = db.getPosts(min_datetime=min_datetime, max_datetime=max_datetime)
    stories = db.getStories(min_datetime=min_datetime, max_datetime=max_datetime)
    topic_highlights = db.getTopicHighlights(min_datetime=min_datetime, max_datetime=max_datetime)
    end_daterange = f'to{max_datetime.strftime('%m-%d')}' if max_datetime != MAX_DATETIME_DEFAULT else ''
    utils.JSONtoCSV(posts, 'data/posts_' + topic_name + '_' + min_datetime.strftime('%m-%d') + end_daterange + '.csv')
    utils.JSONtoCSV(stories, 'data/stories_' + topic_name + '_' + min_datetime.strftime('%m-%d') + end_daterange + '.csv')
    utils.JSONtoCSV(topic_highlights, 'data/topic_highlights_' + topic_name + '_' + min_datetime.strftime('%m-%d') + end_daterange + '.csv')
    print('Overall data output to CSV')

#update story mappings - REFACTOR THIS, SOME HACKY LOGIC
def reMapStories(topic_id, min_datetime, max_datetime=MAX_DATETIME_DEFAULT):
    topic_name = db.getTopics(filters={'topic_id': topic_id})[0]['topic_name']
    db.deleteStories(min_datetime=min_datetime, max_datetime=max_datetime)
    news_posts = db.getPostsForNewsStoryMapping(topic_id, min_datetime=min_datetime, max_datetime=max_datetime)
    mapping = editor.mapNewsPostsToStories(news_posts, topic_name=topic_name)
    stories = []
    #parse and format into story objects for DB
    for story in mapping:
        stories.append({
            'topic_id': topic_id,
            'posts': story['pid'],
            'created_at': min_datetime + timedelta(hours=2)
        })
    db.createStories(stories)
    #fill in story_id column in Post table
    stories = db.getStoriesForTopic(topic_id, min_datetime=min_datetime, max_datetime=max_datetime)
    for story in stories:
        posts = []
        for post_id in story['posts']:
            posts.append({
                'post_id': post_id,
                'story_id': story['story_id']
            })
        db.updatePosts(posts)
    print('Stories mapped and saved to DB')

#PIPELINE PARAMS
##############################################################################################
#Test params
topic_id = 1
max_posts_reddit = 100
max_stories_in_highlights = 5
last2days = datetime.now().timestamp() - 172800 #get current time minus 2 days
custom_min = DATETIME_TODAY_START - timedelta(days = 1)
custom_max = DATETIME_TODAY_START

#RUN PIPELINE
##############################################################################################

#pullPosts(topic_id, max_posts_reddit, min_timestamp=last2days)
#categorizePosts(topic_id, min_datetime=DATETIME_TODAY_START)
#summarizeNewsPosts(topic_id, min_datetime=DATETIME_TODAY_START)
#mapStories(topic_id, min_datetime=DATETIME_TODAY_START)
#storyMappingToCSV(topic_id, min_datetime=DATETIME_TODAY_START)
#summarizeStories(topic_id, min_datetime=DATETIME_TODAY_START)
#rankStories(topic_id, min_datetime=DATETIME_TODAY_START)
#summarizeTopic(topic_id, max_stories=max_stories_in_highlights, min_datetime=DATETIME_TODAY_START)
#storyQAToCSV(topic_id, min_datetime=DATETIME_TODAY_START)
#dailyPipelineToCSV(min_datetime=DATETIME_TODAY_START)

reMapStories(topic_id, min_datetime=custom_min, max_datetime=custom_max)
storyMappingToCSV(topic_id, min_datetime=custom_min, max_datetime=custom_max)