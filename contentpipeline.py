import utils
import db
import sourcer
import editor
import configs
import RAG
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
        summary = editor.generateNewsPostSummary(post=post, feed=feed, topic_prompt_params=topic['topic_prompt_params'])
        retitle = editor.retitleNewsPost(post_summary=summary)
        posts_update.append({
            'post_id': post['post_id'],
            'summary_ml': summary,
            'retitle_ml': retitle
        })
        print(f'SUMMARIZE + RETITLE NEWS POST: {idx+1} of {len(posts)} processed')
    
    db.updatePosts(posts_update)
    print(f'News post summaries + retitles updated in DB')

#filter outdated posts
def filterNewsPosts(topic, min_datetime):
    news_posts = db.getPostsForNewsSummary(topic['topic_id'], min_datetime=min_datetime)
    evaluated_posts = editor.filterOutdatedNews(news_posts, topic_prompt_params=topic['topic_prompt_params'])
    posts_update = []
    for post in evaluated_posts:
        posts_update.append({
            'post_id': post['pid'],
            'outdated_ml': post['outdated']
        })
    db.updatePosts(posts_update)
    print(f'Outdated news posts filtered and updated in DB')

#load news posts, brainstorm themes, select themes, assign posts to themes, save themes to DB
def draftAndMapThemes(topic, min_datetime, brainstorm_loops=3, batch_size=30):
    news_posts = db.getNewsPostsForMapping(topic['topic_id'], min_datetime=min_datetime)

    #brainstorm themes (loop through N times)
    theme_options = []
    for i in range(brainstorm_loops):
        #add characters to news post to get different response from HF API
        news_posts[0]['summary_ml'] = news_posts[0]['summary_ml'] + ' '*i

        brainstorm = editor.brainstormNewsThemes(news_posts, topic_prompt_params=topic['topic_prompt_params'])
        print(f'BRAINSTORM {i+1} \n')
        print(brainstorm)
        for idea in brainstorm:
            if (idea['name'] != "Other") and (' and ' not in idea['name']) and (' & ' not in idea['name']) and not any(option['name'] == idea['name'] for option in theme_options):
                theme_options.append({
                    'id': len(theme_options)+1,
                    'name': idea['name']
                })
    print('THEME OPTIONS: \n')
    print(theme_options)
    
    #select themes from brainstormed options
    selected_themes = editor.selectNewsThemes(news_posts, theme_options=theme_options, topic_prompt_params=topic['topic_prompt_params'])
    
    #sort selected themes so they match id order, add a blank list of posts
    selected_themes = sorted(selected_themes, key=lambda x: x['id'], reverse=False)
    for j in range(len(selected_themes)):
        selected_themes[j]['posts'] = []
    
    print('SELECTED THEMES: \n')
    print(selected_themes)

    #do post assignment to themes in batches
    batched_news_posts = []
    for k in range(0, len(news_posts), batch_size): 
        batched_news_posts.append(news_posts[k:k+batch_size])
    for batch in batched_news_posts:
        mapping = editor.assignNewsPostsToThemes(batch, themes=selected_themes, topic_prompt_params=topic['topic_prompt_params'])
        for post in mapping:
            selected_themes[post['section']-1]['posts'].append(post['pid'])

    #parse and format into theme objects for DB
    theme_updates = []
    for theme in selected_themes:
        theme_updates.append({
            'topic_id': topic['topic_id'],
            'posts': theme['posts'],
            'theme_name_ml': theme['name'],
            'category_ml': 'news'
        })
    db.createThemes(theme_updates)

    #fill in theme_id column in Post table
    themes = db.getThemesForTopic(topic['topic_id'], min_datetime=min_datetime)
    for theme in themes:
        if theme['posts'] != []:
            posts = []
            for post_id in theme['posts']:
                posts.append({
                    'post_id': post_id,
                    'theme_id': theme['theme_id']
                })
            db.updatePosts(posts)
    print('Themes mapped and saved to DB')

#load each theme, dedup and group posts for each theme to unique stories
def groupStories(topic, min_datetime, max_datetime=MAX_DATETIME_DEFAULT):
    news_themes = db.getNewsThemes(topic['topic_id'], min_datetime=min_datetime, max_datetime=max_datetime)
    for theme in news_themes:
        #check if theme has no posts
        if theme['posts'] == []:
            continue

        posts = db.getPosts(min_datetime=min_datetime, max_datetime=max_datetime, filters={'post_id':theme['posts']})
        grouped_stories = editor.groupNewsPostsToStories(posts, topic_prompt_params=topic['topic_prompt_params'])

        grouped_post_ids = []
        stories = []

        #check if empty
        if grouped_stories[0] != {}:
            #parse and format model returned grouped stories
            for story in grouped_stories:
                for pid in story['pid']:
                    grouped_post_ids.append(pid)
                stories.append({
                    'topic_id': topic['topic_id'],
                    'theme_id': theme['theme_id'],
                    'posts': story['pid']
                })
        #parse and format remaining single-post stories
        for post in posts:
            if post['post_id'] not in grouped_post_ids:
                stories.append({
                    'topic_id': topic['topic_id'],
                    'theme_id': theme['theme_id'],
                    'posts': [post['post_id']]
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

#embed news post summaries and save to vector DB
def embedNewsPosts(topic, min_datetime, max_datetime=MAX_DATETIME_DEFAULT):
    news_posts = db.getPostsForEmbedding(topic['topic_id'], min_datetime=min_datetime)
    RAG.embedAndUpsertPosts(news_posts)
    print(f'Posts embedded and saved to vector DB')

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
        #check if theme has no posts
        if theme['posts'] == []:
            continue

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

#embed stories headline and summaries and save to vector DB
def embedStories(topic, min_datetime, max_datetime=MAX_DATETIME_DEFAULT):
    stories = db.getStoriesForEmbedding(topic['topic_id'], min_datetime=min_datetime)
    RAG.embedAndUpsertStories(stories)
    print(f'Stories embedded and saved to vector DB')

#load stories, generate theme
def summarizeThemes(topic, min_datetime, top_k_stories, max_datetime=MAX_DATETIME_DEFAULT):
    themes = db.getNewsThemes(topic['topic_id'], min_datetime=min_datetime)
    for theme in themes:
        #check if theme has no posts
        if theme['posts'] == []:
            continue
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
        if theme['posts'] == []:
            continue
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
    brainstorm_loops = 3
    top_k_stories = 3
    topic = db.getTopics(filters={'topic_id': topic_id})[0]
    topic['topic_prompt_params']['topic_name'] = topic['topic_name']

    #db.deleteStories(min_datetime=DATETIME_TODAY_START)
    #db.deleteThemes(min_datetime=DATETIME_TODAY_START)

    #pullPosts(topic, max_posts_reddit, min_timestamp=DATETIME_TODAY_START.timestamp())
    #categorizePosts(topic, min_datetime=DATETIME_TODAY_START)
    #summarizeNewsPosts(topic, min_datetime=DATETIME_TODAY_START)
    #filterNewsPosts(topic, min_datetime=DATETIME_TODAY_START)
    draftAndMapThemes(topic, brainstorm_loops=brainstorm_loops, min_datetime=DATETIME_TODAY_START)
    groupStories(topic, min_datetime=DATETIME_TODAY_START)
    mappingToCSV(topic, min_datetime=DATETIME_TODAY_START)
    summarizeStories(topic, min_datetime=DATETIME_TODAY_START)
    rankStories(topic, min_datetime=DATETIME_TODAY_START)
    summarizeThemes(topic, top_k_stories=top_k_stories, min_datetime=DATETIME_TODAY_START)
    summarizeTopic(topic, min_datetime=DATETIME_TODAY_START)
    storyQAToCSV(topic, min_datetime=DATETIME_TODAY_START)

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

#topic_id = 1
#topic = db.getTopics(filters={'topic_id': topic_id})[0]
#topic['topic_prompt_params']['topic_name'] = topic['topic_name']
#custom_min = DATETIME_TODAY_START - timedelta(days = 1)
#custom_max = DATETIME_TODAY_START
#reMapStories(topic, min_datetime=custom_min, max_datetime=custom_max)
#storyMappingToCSV(topic, min_datetime=custom_min, max_datetime=custom_max)
#summarizeNewsPosts(topic, min_datetime=custom_min, max_datetime=custom_max)

#mapStories(topic, min_datetime=custom_min, max_datetime=custom_max)
#mappingToCSV(topic, min_datetime=custom_min)