import utils
import db
import sourcer
import editor
import promptconfigs
import configs
import time
from datetime import date

#CONFIGS
##############################################################################################
#Test params
topic_id = 1
topic_name = 'Formula 1'
subreddit = 'formula1'
max_posts = 50
last2days = time.time() - 172800 #get current time minus 2 days

#File paths
PATH_POSTS_REDDIT_CSV = 'data/reddit_test_' + subreddit + "_" + date.today().strftime('%m-%d') + '.csv'
PATH_STORIES_CSV = configs.PATH_STORIES_CSV
PATH_TOPIC_SUMMARIES_CSV = 'data/topic_summary_' + date.today().strftime('%m-%d') + '.csv'

#PIPELINE STEPS
##############################################################################################

#get posts, scrape/process external links, save to DB
def pullPosts():
    #get topic feeds
    feeds = db.getFeedsForTopic(topic_id)
    parsed_posts = []

    #pull and process posts for each feed
    for feed in feeds:
        if feed['feed_type'] == 'subreddit':
            parsed_posts = parsed_posts + sourcer.parseFeedReddit(topic_id=topic_id, feed_id=feed['feed_id'], newer_than_datetime=last2days, max_posts=max_posts, printstats=True)
        elif feed['feed_type'] == 'rss':
            parsed_posts = parsed_posts + sourcer.parseFeedRSS(topic_id=topic_id, feed_id=feed['feed_id'], newer_than_datetime=last2days)

    #save to DB
    db.createPosts(parsed_posts)
    print("Posts pulled and saved to DB")

#load posts, classify category using model, update in DB
def categorizePosts():
    posts = db.getPostsForCategorize(topic_id)
    feed_ids = [post['feed_id'] for post in posts]
    feeds = db.getFeedsForPosts(feed_ids)
    posts_update = []

    for idx, post in enumerate(posts):
        feed = [feed for feed in feeds if feed['feed_id'] == post['feed_id']][0]
        category = editor.classifyPost(post=post, feed=feed, prompt_config=promptconfigs.CLASSIFIER_PROMPTS['categorize'])
        posts_update.append({
            'post_id': post['post_id'],
            'category_ml': category
        })
        print(f'CATEGORIZE POSTS: {idx+1} of {len(posts)} processed')
    
    db.updatePosts(posts_update)
    print(f'Post categories updated in DB')

#load news posts, generate summary, update in DB
def summarizeNewsPosts():
    posts = db.getPostsForNewsSummary(topic_id)
    feed_ids = [post['feed_id'] for post in posts]
    feeds = db.getFeedsForPosts(feed_ids)
    posts_update = []

    for idx, post in enumerate(posts):
        feed = [feed for feed in feeds if feed['feed_id'] == post['feed_id']][0]
        summary = editor.generateNewsPostSummary(post=post, feed=feed, prompt_config=promptconfigs.SUMMARIZER_PROMPTS['news'])
        posts_update.append({
            'post_id': post['post_id'],
            'summary_ml': summary
        })
        print(f'SUMMARIZE NEWS POST: {idx+1} of {len(posts)} processed')
    
    db.updatePosts(posts_update)
    print(f'News post summaries updated in DB')

#load news posts, group into stories, save stories to DB
def mapStories():
    news_posts = db.getPostsForNewsStoryMapping(topic_id)
    mapping = editor.mapNewsPostsToStories(news_posts, prompt_config=promptconfigs.COLLATION_PROMPTS['group_headlines_news'])
    stories = []
    #parse and format into story objects for DB
    for story in mapping:
        stories.append({
            'topic_id': topic_id,
            'posts': story['hid']
        })
    db.createStories(stories)
    #fill in story_id column in Post table
    stories = db.getStoriesForTopic(topic_id)
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
def summarizeStories():
    stories = db.getStoriesForTopic(topic_id)
    story_updates = []

    for idx, story in enumerate(stories):
        posts = db.getPostsForStorySummary(story['story_id'])
        summary, posts_summarized = editor.generateStorySummary(posts, prompt_config=promptconfigs.SUMMARIZER_PROMPTS['story_summary_news'])
        story_updates.append({
            'story_id': story['story_id'],
            'posts_summarized': posts_summarized,
            'summary_ml': summary
        })
        print(f'SUMMARIZE STORY: {idx+1} of {len(stories)} processed')

    db.updateStories(story_updates)
    print(f'Story summaries updated in DB')

#load stories, generate topic summary
def summarizeTopic():
    stories = db.getStoriesForTopicSummary(topic_id)
    topic_highlights = [{
        'topic_id': topic_id,
        'summary_ml': editor.generateTopicSummary(stories, prompt_config=promptconfigs.SUMMARIZER_PROMPTS['topic_summary_news'])
    }]

    db.createTopicHighlight(topic_highlights)
    print(f'Topic summary saved to DB')


#RUN PIPELINE
##############################################################################################
    
#pullPosts()
#categorizePosts()
#summarizeNewsPosts()
#mapStories()
#summarizeStories()
#summarizeTopic()