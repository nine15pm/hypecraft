import utils
import db
import sourcer
import editor
import configs
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
def pullPosts(topic, max_posts_reddit, min_timestamp):
    #get topic feeds
    feeds = db.getFeedsForTopic(topic['topic_id'])
    parsed_posts = []

    #pull and process posts for each feed
    for feed in feeds:
        if feed['feed_type'] == 'rss':
            parsed_posts = parsed_posts + sourcer.parseFeedRSS(topic_id=topic['topic_id'], feed_id=feed['feed_id'], min_timestamp=min_timestamp)
        elif feed['feed_type'] == 'subreddit':
            parsed_posts = parsed_posts + sourcer.parseFeedReddit(topic_id=topic['topic_id'], feed_id=feed['feed_id'], min_timestamp=min_timestamp, max_posts=max_posts_reddit, printstats=True)

    #save to DB
    db.createPosts(parsed_posts)
    print("Posts pulled and saved to DB")

#load posts, classify category using model, update in DB
def categorizePosts(topic, min_datetime, max_datetime=MAX_DATETIME_DEFAULT):
    posts = db.getPostsForCategorize(topic['topic_id'], min_datetime=min_datetime, max_datetime=max_datetime)
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

#load news posts, generate summary, generate retitle, update in DB
def summarizeNewsPosts(topic, min_datetime, max_datetime=MAX_DATETIME_DEFAULT):
    posts = db.getPostsForNewsSummary(topic['topic_id'], min_datetime=min_datetime, max_datetime=max_datetime)
    feed_ids = [post['feed_id'] for post in posts]
    feeds = db.getFeedsForPosts(feed_ids)
    posts_update = []

    for idx, post in enumerate(posts):
        feed = [feed for feed in feeds if feed['feed_id'] == post['feed_id']][0]
        summary = editor.generateNewsPostSummary(post=post, feed=feed)
        retitle = editor.retitleNewsPost(post_summary=summary)
        posts_update.append({
            'post_id': post['post_id'],
            'summary_ml': summary,
            'retitle_ml': retitle
        })
        print(f'SUMMARIZE + RETITLE NEWS POST: {idx+1} of {len(posts)} processed')
    
    db.updatePosts(posts_update)
    print(f'News post summaries + retitles updated in DB')

#load news posts, group into themes, save themes to DB
def mapThemes(topic, min_datetime):
    news_posts = db.getNewsPostsForMapping(topic['topic_id'], min_datetime=min_datetime)
    mapping = editor.mapNewsPostsToThemes(news_posts, topic_prompt_params=topic['topic_prompt_params'])
    themes = []
    #parse and format into theme objects for DB
    for theme in mapping:
        themes.append({
            'topic_id': topic['topic_id'],
            'posts': theme['pid'],
            'theme_name_ml': theme['theme'],
            'category_ml': 'news'
        })
    db.createThemes(themes)
    #fill in theme_id column in Post table
    themes = db.getThemesForTopic(topic['topic_id'], min_datetime=min_datetime)
    for theme in themes:
        posts = []
        for post_id in theme['posts']:
            posts.append({
                'post_id': post_id,
                'theme_id': theme['theme_id']
            })
        db.updatePosts(posts)
    print('Themes mapped and saved to DB')

#load each theme, dedup and map posts for each theme to unique stories
def mapStories(topic, min_datetime, max_datetime=MAX_DATETIME_DEFAULT):
    news_themes = db.getNewsThemes(topic['topic_id'], min_datetime=min_datetime, max_datetime=max_datetime)
    for theme in news_themes:
        posts = db.getPosts(min_datetime=min_datetime, max_datetime=max_datetime, filters={'post_id':theme['posts']})
        mapping = editor.mapNewsPostsToStories(posts, topic_prompt_params=topic['topic_prompt_params'])
        stories = []
        #parse and format into story objects for DB
        for story in mapping:
            stories.append({
                'topic_id': topic['topic_id'],
                'theme_id': theme['theme_id'],
                'posts': story['pid']
            })
        db.createStories(stories)
        #add newly created story ids to Theme table
        story_id_list = [story['story_id'] for story in db.getStoriesForTheme(theme['theme_id'], min_datetime=min_datetime, max_datetime=max_datetime)]
        theme_updates = [{
                'theme_id': theme['theme_id'],
                'stories': story_id_list
        }]
        db.updateThemes(theme_updates)
        #fill in story_id column in Post table
        stories = db.getStoriesForTheme(theme['theme_id'], min_datetime=min_datetime, max_datetime=max_datetime)
        for story in stories:
            posts = []
            for post_id in story['posts']:
                posts.append({
                    'post_id': post_id,
                    'story_id': story['story_id']
                })
            db.updatePosts(posts)
        print(f'Stories for theme "{theme['theme_name_ml']}" mapped and saved to DB')

#load stories, generate story summary, update in DB
def summarizeStories(topic, min_datetime, max_datetime=MAX_DATETIME_DEFAULT):
    stories = db.getStoriesForTopic(topic['topic_id'], min_datetime=min_datetime, max_datetime=max_datetime)
    story_updates = []

    for idx, story in enumerate(stories):
        try:
            posts = db.getPostsForStorySummary(story['posts'])
            summary, posts_summarized = editor.generateStorySummary(posts, topic_prompt_params=topic['topic_prompt_params'])
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

def rankStories(topic, min_datetime, max_datetime=MAX_DATETIME_DEFAULT):
    themes = db.getNewsThemes(topic['topic_id'], min_datetime=min_datetime)
    for theme in themes:
        stories = db.getStoriesForTheme(theme['theme_id'], min_datetime=min_datetime, max_datetime=max_datetime)
        stories_scores = editor.scoreNewsStories(stories, topic_prompt_params=topic['topic_prompt_params'])
        story_updates = []

        for story in stories_scores:
            story_updates.append({
                'story_id': story['sid'],
                'daily_i_score_ml': story['i_score']
            })

        db.updateStories(story_updates)
        print(f'Stories for theme "{theme['theme_name_ml']}" scored and i_scores updated in DB')

#load stories, generate theme
def summarizeThemes(topic, min_datetime, top_k_stories, max_datetime=MAX_DATETIME_DEFAULT):
    themes = db.getNewsThemes(topic['topic_id'], min_datetime=min_datetime)
    for theme in themes:
        stories = db.getStoriesForTheme(theme['theme_id'], min_datetime=min_datetime, max_datetime=max_datetime)
        stories = sorted(stories, key=lambda story: story['daily_i_score_ml'], reverse=True)
        stories = stories[:top_k_stories] if len(stories) > top_k_stories else stories
    
        theme_updates = [{
            'theme_id': theme['theme_id'],
            'summary_ml': editor.generateThemeSummary(stories, topic_prompt_params=topic['topic_prompt_params'])
        }]
        db.updateThemes(theme_updates)
    print(f'Theme summaries saved to DB')

#load stories, generate topic summary
def summarizeTopic(topic, min_datetime, max_datetime=MAX_DATETIME_DEFAULT):
    themes = db.getNewsThemes(topic['topic_id'], min_datetime=min_datetime)
    highlight_stories = []
    for theme in themes:
        stories = db.getStoriesForTheme(theme['theme_id'], min_datetime=min_datetime, max_datetime=max_datetime)
        stories = sorted(stories, key=lambda story: story['daily_i_score_ml'], reverse=True)
        highlight_stories.append(stories[0])
    
    topic_highlights = [{
        'topic_id': topic['topic_id'],
        'summary_ml': editor.generateTopicSummary(highlight_stories, topic_prompt_params=topic['topic_prompt_params'])
    }]

    db.createTopicHighlight(topic_highlights)
    print(f'Topic summary saved to DB')

#CSV dump for checking theme and story mapping
def mappingToCSV(topic, min_datetime, max_datetime=MAX_DATETIME_DEFAULT):
    mapping = []
    themes = db.getThemesForTopic(topic['topic_id'], min_datetime=min_datetime, max_datetime=max_datetime)
    for theme in themes:
        stories = db.getStoriesForTheme(theme['theme_id'], min_datetime=min_datetime, max_datetime=max_datetime)
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
                'theme': theme['theme_name_ml'],
                'story_id': story['story_id'],
                'post_ids': post_id_str,
                'post_links': post_link_str,
                'post_headlines': headlines_str
            })
    end_daterange = f'to{max_datetime.strftime('%m-%d')}' if max_datetime != MAX_DATETIME_DEFAULT else ''
    utils.JSONtoCSV(mapping, 'data/story_mapping_' + topic['topic_name'] + '_' + min_datetime.strftime('%m-%d') + end_daterange + '.csv')
    print('Mapping output to CSV')

#CSV dump for QA story summary content
def storyQAToCSV(topic, min_datetime, max_datetime=MAX_DATETIME_DEFAULT):
    story_summary_qa = []
    themes = db.getThemesForTopic(topic['topic_id'], min_datetime=min_datetime, max_datetime=max_datetime)
    for theme in themes:
        #skip the "other" theme - REFACTOR LOGIC LATER
        if theme['theme_name_ml'] == 'Other':
            continue

        stories = db.getStoriesForTheme(theme['theme_id'], min_datetime=min_datetime, max_datetime=max_datetime)
        for story in stories:
            posts = db.getPostsForStoryQA(story['posts_summarized'])
            QA_json = {
                'story_id': story['story_id'],
                'theme': theme['theme_name_ml'],
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
    utils.JSONtoCSV(story_summary_qa, 'data/story_summary_QA_' + topic['topic_name'] + '_' + min_datetime.strftime('%m-%d') + end_daterange + '.csv')
    print('Story QA output to CSV')

#RUN PIPELINE
##############################################################################################
def main():
    #Pipeline params
    topic_id = 1
    max_posts_reddit = 100
    last2days = datetime.now().timestamp() - 172800 #get current time minus 2 days
    top_k_stories = 3
    topic = db.getTopics(filters={'topic_id': topic_id})[0]
    topic['topic_prompt_params']['topic_name'] = topic['topic_name']

    #pullPosts(topic, max_posts_reddit, min_timestamp=last2days)
    #categorizePosts(topic, min_datetime=DATETIME_TODAY_START)
    #summarizeNewsPosts(topic, min_datetime=DATETIME_TODAY_START)
    #mapThemes(topic, min_datetime=DATETIME_TODAY_START)
    #mapStories(topic, min_datetime=DATETIME_TODAY_START)
    #mappingToCSV(topic, min_datetime=DATETIME_TODAY_START)
    #summarizeStories(topic, min_datetime=DATETIME_TODAY_START)
    #rankStories(topic, min_datetime=DATETIME_TODAY_START)
    #summarizeThemes(topic, top_k_stories=top_k_stories, min_datetime=DATETIME_TODAY_START)
    #summarizeTopic(topic, min_datetime=DATETIME_TODAY_START)
    #storyQAToCSV(topic, min_datetime=DATETIME_TODAY_START)

if __name__ == '__main__':
    main()

#TEMP ARCHIVE AND REMAPPING
##############################################################################################

#CSV dumps for overall data
def dailyPipelineToCSV(topic, min_datetime, max_datetime=MAX_DATETIME_DEFAULT):
    topic_name = db.getTopics(filters={'topic_id': topic['topic_id']})[0]['topic_name']
    #general data dump
    posts = db.getPosts(min_datetime=min_datetime, max_datetime=max_datetime)
    stories = db.getStories(min_datetime=min_datetime, max_datetime=max_datetime)
    topic_highlights = db.getTopicHighlights(min_datetime=min_datetime, max_datetime=max_datetime)
    end_daterange = f'to{max_datetime.strftime('%m-%d')}' if max_datetime != MAX_DATETIME_DEFAULT else ''
    utils.JSONtoCSV(posts, 'data/posts_' + topic_name + '_' + min_datetime.strftime('%m-%d') + end_daterange + '.csv')
    utils.JSONtoCSV(stories, 'data/stories_' + topic_name + '_' + min_datetime.strftime('%m-%d') + end_daterange + '.csv')
    utils.JSONtoCSV(topic_highlights, 'data/topic_highlights_' + topic_name + '_' + min_datetime.strftime('%m-%d') + end_daterange + '.csv')
    print('Overall data output to CSV')

topic_id = 1
topic = db.getTopics(filters={'topic_id': topic_id})[0]
topic['topic_prompt_params']['topic_name'] = topic['topic_name']
custom_min = DATETIME_TODAY_START - timedelta(days = 1)
custom_max = DATETIME_TODAY_START
#reMapStories(topic, min_datetime=custom_min, max_datetime=custom_max)
#storyMappingToCSV(topic, min_datetime=custom_min, max_datetime=custom_max)
#summarizeNewsPosts(topic, min_datetime=custom_min, max_datetime=custom_max)

#mapStories(topic, min_datetime=custom_min, max_datetime=custom_max)
#mappingToCSV(topic, min_datetime=custom_min)