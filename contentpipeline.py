import utils
import db
import sourcer
import editor
import configs
import eventlogger
import RAG
import trendscoring
import json
import atexit
from time import sleep
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
def pullPosts(topic, max_posts_reddit, min_timestamp, min_datetime):
    #get topic feeds
    feeds = db.getFeedsForTopic(topic['topic_id'])
    parsed_posts = []

    #pull and process posts for each feed
    for feed in feeds:
        if feed['feed_type'] == 'rss':
            parsed_posts += sourcer.parseFeedRSS(topic_id=topic['topic_id'], feed_id=feed['feed_id'], min_timestamp=min_timestamp)
        elif feed['feed_type'] == 'subreddit':
            parsed_posts += sourcer.parseFeedReddit(topic_id=topic['topic_id'], feed_id=feed['feed_id'], min_timestamp=min_timestamp, max_posts=max_posts_reddit, printstats=True)
        elif feed['feed_type'] == 'twitterlist':
            parsed_posts += sourcer.parseFeedTwitter(topic_id=topic['topic_id'], feed_id=feed['feed_id'], min_timestamp=min_timestamp, printstats=True)

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
            'theme_description_ml': theme['scope'],
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

        #check if single post only
        if len(posts) == 1:
            grouped_stories = [{
                'sid': 1,
                'pid': [posts[0]['post_id']]
            }]
        else:
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
    news_posts = db.getPostsForEmbed(topic['topic_id'], min_datetime=min_datetime)
    RAG.embedAndUpsertPosts(news_posts)
    print(f'Posts embedded and saved to vector DB')

#load stories, generate story summary, update in DB
def summarizeStories(topic, min_datetime, max_datetime=MAX_DATETIME_DEFAULT):
    stories = db.getStoriesForTopic(topic['topic_id'], min_datetime=min_datetime, max_datetime=max_datetime)
    story_updates = []

    for idx, story in enumerate(stories):
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

    db.updateStories(story_updates)
    print(f'Story summaries updated in DB')

#filter out stories that appeared already in past newsletter and don't have new info
def filterRepeatStories(topic, min_datetime, max_datetime=MAX_DATETIME_DEFAULT, search_limit=5):
    stories = db.getStoriesForTopic(topic['topic_id'], min_datetime=min_datetime, max_datetime=max_datetime)
    story_updates = []
    repeat_count = 0

    for story in stories:
        #search vector DB for past related stories
        match_filters = {
            'topic_id': topic['topic_id'],
            'used_in_newsletter': True
        }
        results = RAG.searchStories(text=f'{story['headline_ml']}\n{story['summary_ml']}', max_results=search_limit, max_datetime=min_datetime, match_filters=match_filters)
        
        if results != []:
            RAG_stories = db.getStories(filters={'story_id': [result['id'] for result in results]})
        
            #filter out any unrelated stories from search results
            filtered_results = editor.filterStoryRAGResults(target_story=story, RAG_stories=RAG_stories, topic_prompt_params=topic['topic_prompt_params'])
        else:
            filtered_results = [{}]

        if filtered_results != [{}]:
            filtered_results = [item['id'] for item in filtered_results]
            RAG_stories = [story for story in RAG_stories if story['story_id'] in filtered_results]
        
            #check if there is any meaningful new info vs. past stories
            new_and_meaningful = editor.filterStoryNewInfo(target_story=story, past_stories=RAG_stories, topic_prompt_params=topic['topic_prompt_params'])[0]['new_and_meaningful']
            
            #update status in DB
            if not new_and_meaningful:
                story_updates.append(
                    {
                        'story_id': story['story_id'],
                        'past_newsletter_repeat': True,
                        'has_past_common_stories': True,
                        'past_common_stories': [story['story_id'] for story in RAG_stories]
                    }
                )
                repeat_count += 1
            else:
                story_updates.append(
                    {
                        'story_id': story['story_id'],
                        'past_newsletter_repeat': False,
                        'has_past_common_stories': True,
                        'past_common_stories': [story['story_id'] for story in RAG_stories]
                    }
                )
    if story_updates != []:
        db.updateStories(story_updates)
    print(f'Stories checked for repeat vs past newsletters, {repeat_count} out of {len(stories)} repeats')

#rewrite summaries of stories with past related stories to continue the narrative
def rewriteStoriesWithPastContext(topic, max_past_context, min_datetime, max_datetime=MAX_DATETIME_DEFAULT):
    stories = db.getStories(min_datetime=min_datetime, max_datetime=max_datetime, filters={'topic_id':topic['topic_id'], 'past_newsletter_repeat': False, 'has_past_common_stories': True})
    story_updates = []

    #get past common stories (2 most recent) and generate new summary
    for story in stories:
        past_stories = db.getStories(filters={'story_id': story['past_common_stories']})
        past_stories = sorted(past_stories, key=lambda story: story['newsletter_date'], reverse=True)[:max_past_context]
        new_summary = editor.rewriteStorySummaryPastContext(story=story, past_stories=past_stories, topic_prompt_params=topic['topic_prompt_params'])
        story_updates.append(
            {
                'story_id': story['story_id'],
                'summary_ml': new_summary
            }
        )

    if story_updates != []:
        db.updateStories(story_updates)
    print(f'Stories with past context rewritten')

#re-check assigned theme for each story, revise if there is a better fit
def checkAndReviseStoryThemes(topic, min_datetime, max_datetime=MAX_DATETIME_DEFAULT):
    themes = db.getNewsThemes(topic['topic_id'], min_datetime=min_datetime)
    stories = db.getFilteredStoriesForTopic(topic['topic_id'], min_datetime=min_datetime)

    for story in stories:
        current_theme_name = db.getThemes(filters={'theme_id':story['theme_id']})[0]['theme_name_ml']
        revised_theme = editor.reviseStoryThemes(story=story, current_theme=current_theme_name, themes=themes, topic_prompt_params=topic['topic_prompt_params'])
        story_update = {
            'story_id': story['story_id'],
            'theme_id': revised_theme[0]['section_id']
        }
        db.updateStories(story_update)
    
    #updated story and post ids in theme table
    for theme in themes:
        theme_stories = db.getStoriesForTheme(theme['theme_id'], min_datetime=min_datetime, max_datetime=max_datetime)
        posts_list = []
        for story in theme_stories:
            posts_list += story['posts']
    
        theme_updates = [{
            'theme_id': theme['theme_id'],
            'stories': [story['story_id'] for story in theme_stories],
            'posts': posts_list
        }]

        db.updateThemes(theme_updates)

    print(f'Story theme assignments revised')

#get context for ranking = currently just calc trend score
def getStoryRankingContext(topic, min_datetime, max_datetime=MAX_DATETIME_DEFAULT):
    #get stories with past newsletter repeats filtered out
    stories = db.getFilteredStoriesForTopic(topic['topic_id'], min_datetime=min_datetime)
    story_updates = []

    #generate search query and calc trend score from tweets
    for story in stories:
        print(story['headline_ml'])
        queries_list = editor.generateTweetSearchQueries(story, topic_prompt_params=topic['topic_prompt_params'])
        trend_score = trendscoring.calcTrendScore(queries_list=queries_list, sample_size=10, min_datetime=min_datetime)
    
        #save updates
        story_updates.append({
            'story_id': story['story_id'],
            'trend_score': trend_score
        })

    db.updateStories(story_updates)
    print(f'Story ranking context (trend score) gathered and saved to DB')

#score stories for newsletter ranking order
def rankStories(topic, min_datetime, max_datetime=MAX_DATETIME_DEFAULT):
    themes = db.getNewsThemes(topic['topic_id'], min_datetime=min_datetime)
    for theme in themes:
        #check if theme has no posts
        if theme['posts'] == []:
            continue

        #get stories with past newsletter repeats filtered out
        stories = db.getFilteredStoriesForTheme(theme['theme_id'], min_datetime=min_datetime, max_datetime=max_datetime)

        #score stories
        stories_scores = editor.scoreNewsStories(stories, topic_prompt_params=topic['topic_prompt_params'])
        story_updates = []

        for story in stories_scores:
            #save updates
            story_updates.append({
                'story_id': story['sid'],
                'daily_i_score_ml': story['i_score']
            })

        db.updateStories(story_updates)
        print(f'Stories for theme "{theme['theme_name_ml']}" scored and i_scores updated in DB')

#embed stories headline and summaries and save to vector DB
def embedStories(topic, min_datetime, max_datetime=MAX_DATETIME_DEFAULT):
    stories = db.getStoriesForEmbed(topic['topic_id'], min_datetime=min_datetime)
    RAG.embedAndUpsertStories(stories)
    print(f'Stories embedded and saved to vector DB')

#logic to pick out the stories to be used in each part of the news section (highlights, top stories, radar)
def selectStories(topic, num_highlight_stories, num_top_stories, trend_score_mult, max_radar_stories, min_trend_score, min_i_score, min_datetime, max_datetime=MAX_DATETIME_DEFAULT):
    stories = db.getFilteredStoriesForTopic(topic_id=topic['topic_id'], min_datetime=min_datetime, max_datetime=max_datetime)
    themes = db.getNewsThemes(topic['topic_id'], min_datetime=min_datetime)

    #filter out stories that don't meet either min trend score or min i score
    stories = [story for story in stories if story['daily_i_score_ml'] >= min_i_score or story['trend_score'] >= min_trend_score]

    #calculate blended rank score using base of i_score + boost from trend score (only apply boost to stories that meet min i_score)
    for story in stories:
        trend_score = story['trend_score'] if story['trend_score'] > 0 and story['trend_score'] is not None else -1
        if story['daily_i_score_ml'] >= min_i_score:
            story['rank_score'] = story['daily_i_score_ml'] + (trend_score * trend_score_mult)
        else:
            story['rank_score'] = story['daily_i_score_ml']

    #sort stories by rank score
    stories = sorted(stories, key=lambda story: story['rank_score'], reverse=True)

    #take top stories
    if len(stories) > num_highlight_stories:
        highlight_candidates = stories[:num_highlight_stories]
        top_stories = stories[:num_top_stories]
    else:
        highlight_candidates = stories
        top_stories = stories[:num_top_stories] if len(stories) > num_top_stories else stories
    
    #select radar stories
    radar_theme_ids = []
    for theme in themes:
        #get theme stories
        theme_stories = [story for story in stories if story['theme_id'] == theme['theme_id']]
        #filter out already used stories in top and highlights
        theme_stories = [story for story in theme_stories if story not in highlight_candidates]
        #check if no stories
        if theme_stories == [] or None:
            continue
        #sort by rank score
        theme_stories = sorted(theme_stories, key=lambda story: story['rank_score'], reverse=True)
        #remove if exceeds max number of stories
        theme_stories = theme_stories[:max_radar_stories] if len(theme_stories) > max_radar_stories else theme_stories

        radar_theme_ids.append(theme['theme_id'])
        theme_updates = [{
            'theme_id': theme['theme_id'],
            'radar_stories': [story['story_id'] for story in theme_stories],
            'max_rank_score': max([story['rank_score'] for story in theme_stories])
        }]
        db.updateThemes(theme_updates)

    #save selected stories
    news_sections = [{
        'topic_id': topic['topic_id'],
        'highlight_stories': [story['story_id'] for story in highlight_candidates],
        'top_stories': [story['story_id'] for story in top_stories],
        'radar_themes': radar_theme_ids
    }]
    db.createNewsSections(news_sections)

    #save rank scores for selected stories
    story_updates = []
    for story in highlight_candidates:
        story_updates.append(
            {
                'story_id': story['story_id'],
                'rank_score': story['rank_score']
            }
        )
    db.updateStories(story_updates)

    print(f'Highlight, top, and radar stories selected and saved to DB')

#load stories, generate radar summaries
def writeRadar(topic, min_datetime, max_datetime=MAX_DATETIME_DEFAULT):
    themes = db.getNewsThemes(topic['topic_id'], min_datetime=min_datetime)

    for theme in themes:
        stories = db.getStories(min_datetime=min_datetime, max_datetime=max_datetime, filters={'story_id': theme['radar_stories']})
        #check if no stories
        if stories == [] or None:
            continue

        summary_phrase_list = editor.generateRadarSummary(stories, topic_prompt_params=topic['topic_prompt_params'])

        theme_updates = [{
            'theme_id': theme['theme_id'],
            'radar_summary_ml': json.dumps(summary_phrase_list),
            'radar_stories': [story['story_id'] for story in stories]
        }]
        db.updateThemes(theme_updates)
    print(f'Radar summaries saved to DB')

#load stories, generate topic summary bullets, save sorted bullet list
def writeHighlights(topic, min_datetime, max_datetime=MAX_DATETIME_DEFAULT):
    news_section = db.getNewsSections(min_datetime=min_datetime, max_datetime=max_datetime, filters={'topic_id': topic['topic_id']})[0]
    top_story_ids = news_section['highlight_stories']
    top_stories = db.getStories(min_datetime=min_datetime, max_datetime=max_datetime, filters={'story_id': top_story_ids})
    
    bullets_list = editor.generateTopicHighlights(top_stories, topic_prompt_params=topic['topic_prompt_params'])
    
    #get the i_score for each bullet
    for story in top_stories:
        idx = utils.getDictIndex(bullets_list, 'story_id', story['story_id'])
        bullets_list[idx]['rank_score'] = story['rank_score']
    
    #sort bullets list
    bullets_list = sorted(bullets_list, key=lambda bullet: bullet['rank_score'], reverse=True)

    topic_highlights = [{
        'topic_id': topic['topic_id'],
        'stories': top_story_ids,
        'summary_bullets_ml': json.dumps(bullets_list)
    }]

    db.createTopicHighlights(topic_highlights)
    print(f'Topic summary bullets saved to DB')

#RUN PIPELINE
##############################################################################################

PIPELINE_STEPS = [
    'pull_posts',
    'categorize_posts',
    'summarize_news_posts',
    'embed_news_posts',
    'filter_news_posts',
    'draft_map_themes',
    'group_stories',
    'summarize_stories',
    'filter_repeat_stories',
    'rewrite_stories_past_context',
    'get_story_ranking_context',
    'rank_stories',
    'embed_stories',
    'select_stories',
    'write_radar',
    'write_highlights',
]

PIPELINE_PARAMS = {
    'max_retries': 2, #number of times to retry pipeline step if error
    'max_posts_reddit': 100, #limit to total number of posts pulled from 1 subreddit
    'theme_brainstorm_loops': 3, #number of times to re-call model to brainstorm theme options
    'max_past_context': 2, #number of past newsletter stories to give when rewriting summary
    'min_trend_score': 1500, #minimum score to not get filtered out
    'min_i_score': 40, #minimum score to not get filtered out
    'num_highlight_stories': 3, #number of highlights bullets
    'num_top_stories': 1, #number of top stories in top stories block
    'max_radar_stories': 3, #max number of stories per theme in radar block
    'trend_score_mult': 0.01, #multiplier for weighting trend score in ranking
    'RAG_search_limit': 5, #top N results to return from RAG search
}

#get status of current run
def getRunStatus(topic_id, min_datetime=DATETIME_TODAY_START, max_datetime=MAX_DATETIME_DEFAULT) -> dict:
    all_events = eventlogger.getPipelineStatsEvents(topic_id, min_datetime=min_datetime, max_datetime=max_datetime)
    meta_run_events = [event for event in all_events if event['pipeline_step'] in ['meta_run_start', 'meta_run_end', 'meta_run_exit']]

    #sort for latest event
    meta_run_events = sorted(meta_run_events, key=lambda event: event['created_at'], reverse=True) if meta_run_events != [] else meta_run_events

    #if no run events, then run not started
    if meta_run_events == []:
        status = {
            'run_status': 'not_started',
            'run_start_time': None,
            'run_end_time': None,
            'msg': None
        }
    #if latest event is run start event, determine whether run is in progress or has error
    elif meta_run_events[0]['pipeline_step'] == 'meta_run_start':
        meta_start_events = sorted([event for event in all_events if event['pipeline_step'] == 'meta_run_start'], key=lambda event: event['created_at'], reverse=True)
        detail_events = sorted([event for event in all_events if event['pipeline_step'] in PIPELINE_STEPS], key=lambda event: event['created_at'], reverse=True)
        #if error was last detail event, then overall status is error
        if detail_events[0]['event'] == 'error':
            msg = f'{detail_events[0]['payload']}'
            status = {
                'run_status': 'incomplete',
                'run_start_time': datetime.strftime(meta_start_events[0]['created_at'], "%Y-%m-%d %I:%M"),
                'run_end_time': datetime.strftime(detail_events[0]['created_at'], "%Y-%m-%d %I:%M"),
                'msg': msg
            }
        #otherwise overall status is in progress
        else:
            status = {
                'run_status': 'in_progress',
                'run_start_time': datetime.strftime(meta_run_events[0]['created_at'], "%Y-%m-%d %I:%M"),
                'run_end_time': None,
                'msg': None
            }
    #if latest event is exit event, then run was halted
    elif meta_run_events[0]['pipeline_step'] == 'meta_run_exit':
        meta_start_events = sorted([event for event in all_events if event['pipeline_step'] == 'meta_run_start'], key=lambda event: event['created_at'], reverse=True)
        detail_events = sorted([event for event in all_events if event['pipeline_step'] in PIPELINE_STEPS], key=lambda event: event['created_at'], reverse=True)
        if detail_events[0]['event'] == 'error':
            msg = f'{detail_events[0]['payload']}'
        else:
            msg = 'Stopped by user'
        status = {
            'run_status': 'incomplete',
            'run_start_time': datetime.strftime(meta_start_events[0]['created_at'], "%Y-%m-%d %I:%M"),
            'run_end_time': datetime.strftime(meta_run_events[0]['created_at'], "%Y-%m-%d %I:%M"),
            'msg': msg
        }
    #if latest event is run end event, then run is complete
    elif meta_run_events[0]['pipeline_step'] == 'meta_run_end':
        meta_start_events = sorted([event for event in all_events if event['pipeline_step'] == 'meta_run_start'], key=lambda event: event['created_at'], reverse=True)
        status = {
            'run_status': 'complete',
            'run_start_time': datetime.strftime(meta_start_events[0]['created_at'], "%Y-%m-%d %I:%M"),
            'run_end_time': datetime.strftime(meta_run_events[0]['created_at'], "%Y-%m-%d %I:%M"),
            'msg': None
        }
    return status

#get latest pipeline stats for date
def getPipelineStats(topic_id, min_datetime=DATETIME_TODAY_START, max_datetime=MAX_DATETIME_DEFAULT) -> list[dict]:
    all_events = eventlogger.getPipelineStatsEvents(topic_id, min_datetime=min_datetime, max_datetime=max_datetime)
    pipeline_status = []
    for step_name in PIPELINE_STEPS:
        #filter to events for step
        step_events = [event for event in all_events if event['pipeline_step'] == step_name]
        if step_events == []:
            #if no events for step, then set status to not started
            status = 'not_started'
            attempts = None
            duration = None
            detail = None
        else:
            #sort latest event first, then set status depending on event type
            step_events = sorted(step_events, key=lambda event: event['created_at'], reverse=True)
            if step_events[0]['event'] == 'start':
                status = 'in_progress'
            elif step_events[0]['event'] == 'error':
                status = 'error'
            elif step_events[0]['event'] == 'success':
                status = 'success'

            #filter to specific events
            start_events = [event for event in step_events if event['event'] == 'start']
            error_events = [event for event in step_events if event['event'] == 'error']

            #calculate duration if end status
            if status == 'success' or 'error':
                end_event_datetime = step_events[0]['created_at']
                start_event_datetime = start_events[0]['created_at']
                #calculate run time in seconds
                duration = (end_event_datetime - start_event_datetime).total_seconds()
            else:
                duration = None
            
            #count number of attempts if applicable
            attempts = len(start_events) if start_events != [] else 0

            #add error message if applicable
            detail = f'[ERROR: {error_events[0]['payload']['type']}] {error_events[0]['payload']['error']}' if error_events != [] else None
        
        pipeline_status.append(
            {
                'step_name': step_name,
                'status': status,
                'attempts': attempts,
                'duration': duration,
                'detail': detail,
            }
        )
    return pipeline_status

#function to run when pipeline run is exited
def exitHandler(topic_id, min_datetime, content_date):
    if getRunStatus(topic_id=topic_id, min_datetime=min_datetime) == 'in_progress':
        eventlogger.logPipelineEvent(topic_id = topic_id, content_date = content_date, step_name = 'meta_run_exit', event = 'exit')

#main function to run pipeline
def runPipeline(topic_id, min_datetime=DATETIME_TODAY_START, max_datetime=MAX_DATETIME_DEFAULT, pipeline_params=PIPELINE_PARAMS, rerun=False):
    #register exit handler function
    atexit.register(exitHandler, topic_id=topic_id, min_datetime=min_datetime, content_date=min_datetime.date())

    msg = 'Pipeline run started'
    eventlogger.logPipelineEvent(topic_id = topic_id, content_date = min_datetime.date(), step_name = 'meta_run_start', event = 'start', payload = json.dumps({'msg': msg}))

    #Set params
    max_retries = pipeline_params['max_retries']
    max_posts_reddit = pipeline_params['max_posts_reddit']
    brainstorm_loops = pipeline_params['theme_brainstorm_loops']
    max_past_context = pipeline_params['max_past_context']
    min_trend_score = pipeline_params['min_trend_score']
    min_i_score = pipeline_params['min_i_score']
    num_highlight_stories = pipeline_params['num_highlight_stories']
    num_top_stories = pipeline_params['num_top_stories']
    max_radar_stories = pipeline_params['max_radar_stories']
    trend_score_mult = pipeline_params['trend_score_mult']
    RAG_search_limit = pipeline_params['RAG_search_limit']
    min_timestamp = min_datetime.timestamp()
    topic = db.getTopics(filters={'topic_id': topic_id})[0]
    topic['topic_prompt_params']['topic_name'] = topic['topic_name']

    #get pipeline stats to figure out which step to start from
    stats = getPipelineStats(topic_id=topic_id, min_datetime=min_datetime, max_datetime=max_datetime)

    #check if run is currently in progress
    if any(step['status'] == 'in progress' for step in stats):
        msg = 'Cannot start run, pipeline run is already in progress'
        eventlogger.logPipelineEvent(topic_id = topic_id, content_date = min_datetime.date(), step_name = 'meta_run_start', event = 'start_fail', payload = json.dumps({'msg': msg}))
        return msg
    
    #check if all steps are success status and rerun is false
    if all(step['status'] == 'success' for step in stats) and rerun == False:
        msg = 'Cannot start run, all pipeline steps already completed successfully'
        eventlogger.logPipelineEvent(topic_id = topic_id, content_date = min_datetime.date(), step_name = 'meta_run_start', event = 'start_fail', payload = json.dumps({'msg': msg}))
        return msg

    #set which steps to run
    run_status = {}
    for step in stats:
        should_run = True if step['status'] != 'success' else False
        run_status[step['step_name']] = should_run
    
    #RUN STEP: Pull posts (no retries)
    cur_step = 'pull_posts'
    if run_status[cur_step]:
        try:
            eventlogger.logPipelineEvent(topic_id = topic_id, content_date = min_datetime.date(), step_name = cur_step, event = 'start')
            pullPosts(topic, max_posts_reddit, min_timestamp=min_timestamp, min_datetime=min_datetime)
            eventlogger.logPipelineEvent(topic_id = topic_id, content_date = min_datetime.date(), step_name = cur_step, event = 'success')
        except Exception as error:
            error_log = json.dumps({'type': type(error).__name__, 'error': str(error)})
            eventlogger.logPipelineEvent(topic_id = topic_id, content_date = min_datetime.date(), step_name = cur_step, event = 'error', payload = error_log)
            raise

    #RUN STEP: Categorize posts into news, discussion, insights, meme, junk, etc. (retry on error)
    cur_step = 'categorize_posts'
    if run_status[cur_step]:
        retry = True
        num_retries = 0
        while retry:
            try:
                eventlogger.logPipelineEvent(topic_id = topic_id, content_date = min_datetime.date(), step_name = cur_step, event = 'start')
                categorizePosts(topic, min_datetime=min_datetime)
                eventlogger.logPipelineEvent(topic_id = topic_id, content_date = min_datetime.date(), step_name = cur_step, event = 'success')
                retry = False
            except Exception as error:
                error_log = json.dumps({'type': type(error).__name__, 'error': str(error)})
                eventlogger.logPipelineEvent(topic_id = topic_id, content_date = min_datetime.date(), step_name = cur_step, event = 'error', payload = error_log)
                if num_retries <= max_retries:
                    num_retries += 1
                else:
                    retry = False
                    raise
    
    #RUN STEP: Summarize and retitle news posts (retry on error)
    cur_step = 'summarize_news_posts'
    if run_status[cur_step]:
        retry = True
        num_retries = 0
        while retry:
            try:
                eventlogger.logPipelineEvent(topic_id = topic_id, content_date = min_datetime.date(), step_name = cur_step, event = 'start')
                summarizeNewsPosts(topic, min_datetime=min_datetime)
                eventlogger.logPipelineEvent(topic_id = topic_id, content_date = min_datetime.date(), step_name = cur_step, event = 'success')
                retry = False
            except Exception as error:
                error_log = json.dumps({'type': type(error).__name__, 'error': str(error)})
                eventlogger.logPipelineEvent(topic_id = topic_id, content_date = min_datetime.date(), step_name = cur_step, event = 'error', payload = error_log)
                if num_retries <= max_retries:
                    num_retries += 1
                else:
                    retry = False
                    raise
    
    #RUN STEP: Store news posts in vector DB for RAG (no retry)
    cur_step = 'embed_news_posts'
    if run_status[cur_step]:
        try:
            eventlogger.logPipelineEvent(topic_id = topic_id, content_date = min_datetime.date(), step_name = cur_step, event = 'start')
            embedNewsPosts(topic=topic, min_datetime=min_datetime)
            eventlogger.logPipelineEvent(topic_id = topic_id, content_date = min_datetime.date(), step_name = cur_step, event = 'success')
        except Exception as error:
            error_log = json.dumps({'type': type(error).__name__, 'error': str(error)})
            eventlogger.logPipelineEvent(topic_id = topic_id, content_date = min_datetime.date(), step_name = cur_step, event = 'error', payload = error_log)
            raise
    
    #RUN STEP: Filter outdated news posts (retry on error)
    cur_step = 'filter_news_posts'
    if run_status[cur_step]:
        retry = True
        num_retries = 0
        while retry:
            try:
                eventlogger.logPipelineEvent(topic_id = topic_id, content_date = min_datetime.date(), step_name = cur_step, event = 'start')
                filterNewsPosts(topic, min_datetime=min_datetime)
                eventlogger.logPipelineEvent(topic_id = topic_id, content_date = min_datetime.date(), step_name = cur_step, event = 'success')
                retry = False
            except Exception as error:
                error_log = json.dumps({'type': type(error).__name__, 'error': str(error)})
                eventlogger.logPipelineEvent(topic_id = topic_id, content_date = min_datetime.date(), step_name = cur_step, event = 'error', payload = error_log)
                if num_retries <= max_retries:
                    num_retries += 1
                else:
                    retry = False
                    raise
    
    #RUN STEP: Draft theme names and map posts to themes (retry on error)
    cur_step = 'draft_map_themes'
    if run_status[cur_step]:
        retry = True
        num_retries = 0
        while retry:
            try:
                eventlogger.logPipelineEvent(topic_id = topic_id, content_date = min_datetime.date(), step_name = cur_step, event = 'start')
                draftAndMapThemes(topic, brainstorm_loops=brainstorm_loops, min_datetime=min_datetime)
                eventlogger.logPipelineEvent(topic_id = topic_id, content_date = min_datetime.date(), step_name = cur_step, event = 'success')
                retry = False
            except Exception as error:
                error_log = json.dumps({'type': type(error).__name__, 'error': str(error)})
                eventlogger.logPipelineEvent(topic_id = topic_id, content_date = min_datetime.date(), step_name = cur_step, event = 'error', payload = error_log)
                db.deleteThemes(min_datetime=min_datetime, filters={'topic_id': topic_id})
                if num_retries <= max_retries:
                    num_retries += 1
                else:
                    retry = False
                    raise
    
    #RUN STEP: Group related and same news posts into stories (retry on error)
    cur_step = 'group_stories'
    if run_status[cur_step]:
        retry = True
        num_retries = 0
        while retry:
            try:
                eventlogger.logPipelineEvent(topic_id = topic_id, content_date = min_datetime.date(), step_name = cur_step, event = 'start')
                groupStories(topic, min_datetime=min_datetime)
                eventlogger.logPipelineEvent(topic_id = topic_id, content_date = min_datetime.date(), step_name = cur_step, event = 'success')
                retry = False
            except Exception as error:
                error_log = json.dumps({'type': type(error).__name__, 'error': str(error)})
                eventlogger.logPipelineEvent(topic_id = topic_id, content_date = min_datetime.date(), step_name = cur_step, event = 'error', payload = error_log)
                db.deleteStories(min_datetime=min_datetime, filters={'topic_id': topic_id})
                if num_retries <= max_retries:
                    num_retries += 1
                else:
                    retry = False
                    raise
    
    #RUN STEP: Summarize news stories (retry on error)
    cur_step = 'summarize_stories'
    if run_status[cur_step]:
        retry = True
        num_retries = 0
        while retry:
            try:
                eventlogger.logPipelineEvent(topic_id = topic_id, content_date = min_datetime.date(), step_name = cur_step, event = 'start')
                summarizeStories(topic, min_datetime=min_datetime)
                eventlogger.logPipelineEvent(topic_id = topic_id, content_date = min_datetime.date(), step_name = cur_step, event = 'success')
                retry = False
            except Exception as error:
                error_log = json.dumps({'type': type(error).__name__, 'error': str(error)})
                eventlogger.logPipelineEvent(topic_id = topic_id, content_date = min_datetime.date(), step_name = cur_step, event = 'error', payload = error_log)
                if num_retries <= max_retries:
                    num_retries += 1
                else:
                    retry = False
                    raise
    
    #RUN STEP: Filter out any news stories previously featured in newsletter (retry on error)
    cur_step = 'filter_repeat_stories'
    if run_status[cur_step]:
        retry = True
        num_retries = 0
        while retry:
            try:
                eventlogger.logPipelineEvent(topic_id = topic_id, content_date = min_datetime.date(), step_name = cur_step, event = 'start')
                filterRepeatStories(topic, min_datetime=min_datetime, search_limit=RAG_search_limit)
                eventlogger.logPipelineEvent(topic_id = topic_id, content_date = min_datetime.date(), step_name = cur_step, event = 'success')
                retry = False
            except Exception as error:
                error_log = json.dumps({'type': type(error).__name__, 'error': str(error)})
                eventlogger.logPipelineEvent(topic_id = topic_id, content_date = min_datetime.date(), step_name = cur_step, event = 'error', payload = error_log)
                if num_retries <= max_retries:
                    num_retries += 1
                else:
                    retry = False
                    raise
    
    #RUN STEP: Rewrite any story summaries that are continuations of prior stories to continue the narrative with past context (retry on error)
    cur_step = 'rewrite_stories_past_context'
    if run_status[cur_step]:
        retry = True
        num_retries = 0
        while retry:
            try:
                eventlogger.logPipelineEvent(topic_id = topic_id, content_date = min_datetime.date(), step_name = cur_step, event = 'start')
                rewriteStoriesWithPastContext(topic, max_past_context=max_past_context, min_datetime=min_datetime)
                eventlogger.logPipelineEvent(topic_id = topic_id, content_date = min_datetime.date(), step_name = cur_step, event = 'success')
                retry = False
            except Exception as error:
                error_log = json.dumps({'type': type(error).__name__, 'error': str(error)})
                eventlogger.logPipelineEvent(topic_id = topic_id, content_date = min_datetime.date(), step_name = cur_step, event = 'error', payload = error_log)
                if num_retries <= max_retries:
                    num_retries += 1
                else:
                    retry = False
                    raise
    
    #RUN STEP: Check story theme assignments and revise if needed (retry on error)
    #cur_step = 'check_revise_story_themes'
    #if run_status[cur_step]:
    #    retry = True
    #    num_retries = 0
    #    while retry:
    #        try:
    #            eventlogger.logPipelineEvent(topic_id = topic_id, content_datetime = min_datetime.date(), step_name = cur_step, event = 'start')
    #            checkAndReviseStoryThemes(topic, min_datetime=min_datetime)
    #            eventlogger.logPipelineEvent(topic_id = topic_id, content_datetime = min_datetime.date(), step_name = cur_step, event = 'success')
    #            retry = False
    #        except Exception as error:
    #            error_log = json.dumps({'type': type(error).__name__, 'error': str(error)})
    #            eventlogger.logPipelineEvent(topic_id = topic_id, content_datetime = min_datetime.date(), step_name = cur_step, event = 'error', payload = error_log)
    #            if num_retries <= max_retries:
    #                num_retries += 1
    #            else:
    #                retry = False
    #                raise

    #RUN STEP: Get data needed to calc trend score and rank stories (retry on error)
    cur_step = 'get_story_ranking_context'
    if run_status[cur_step]:
        retry = True
        num_retries = 0
        while retry:
            try:
                eventlogger.logPipelineEvent(topic_id = topic_id, content_date = min_datetime.date(), step_name = cur_step, event = 'start')
                getStoryRankingContext(topic, min_datetime=min_datetime)
                eventlogger.logPipelineEvent(topic_id = topic_id, content_date = min_datetime.date(), step_name = cur_step, event = 'success')
                retry = False
            except Exception as error:
                error_log = json.dumps({'type': type(error).__name__, 'error': str(error)})
                eventlogger.logPipelineEvent(topic_id = topic_id, content_date = min_datetime.date(), step_name = cur_step, event = 'error', payload = error_log)
                if num_retries <= max_retries:
                    num_retries += 1
                else:
                    retry = False
                    raise
    
    #RUN STEP: Score stories using model (retry on error)
    cur_step = 'rank_stories'
    if run_status[cur_step]:
        retry = True
        num_retries = 0
        while retry:
            try:
                eventlogger.logPipelineEvent(topic_id = topic_id, content_date = min_datetime.date(), step_name = cur_step, event = 'start')
                rankStories(topic, min_datetime=min_datetime)
                eventlogger.logPipelineEvent(topic_id = topic_id, content_date = min_datetime.date(), step_name = cur_step, event = 'success')
                retry = False
            except Exception as error:
                error_log = json.dumps({'type': type(error).__name__, 'error': str(error)})
                eventlogger.logPipelineEvent(topic_id = topic_id, content_date = min_datetime.date(), step_name = cur_step, event = 'error', payload = error_log)
                if num_retries <= max_retries:

                    num_retries += 1
                else:
                    retry = False
                    raise
    
    #RUN STEP: Embed news stories in vector DB for RAG (no retry)
    cur_step = 'embed_stories'
    if run_status[cur_step]:
        try:
            eventlogger.logPipelineEvent(topic_id = topic_id, content_date = min_datetime.date(), step_name = cur_step, event = 'start')
            embedStories(topic=topic, min_datetime=min_datetime)
            eventlogger.logPipelineEvent(topic_id = topic_id, content_date = min_datetime.date(), step_name = cur_step, event = 'success')
            retry = False
        except Exception as error:
            error_log = json.dumps({'type': type(error).__name__, 'error': str(error)})
            eventlogger.logPipelineEvent(topic_id = topic_id, content_date = min_datetime.date(), step_name = cur_step, event = 'error', payload = error_log)
            raise
    
    #RUN STEP: Select and order stories for each section of newsletter (no retry)
    cur_step = 'select_stories'
    if run_status[cur_step]:
        try:
            eventlogger.logPipelineEvent(topic_id = topic_id, content_date = min_datetime.date(), step_name = cur_step, event = 'start')
            selectStories(topic, trend_score_mult=trend_score_mult, num_highlight_stories=num_highlight_stories, num_top_stories=num_top_stories, min_i_score=min_i_score, min_trend_score=min_trend_score, max_radar_stories=max_radar_stories, min_datetime=min_datetime)
            eventlogger.logPipelineEvent(topic_id = topic_id, content_date = min_datetime.date(), step_name = cur_step, event = 'success')
            retry = False
        except Exception as error:
            error_log = json.dumps({'type': type(error).__name__, 'error': str(error)})
            eventlogger.logPipelineEvent(topic_id = topic_id, content_date = min_datetime.date(), step_name = cur_step, event = 'error', payload = error_log)
            db.deleteNewsSection(min_datetime=min_datetime, filters={'topic_id': topic_id})
            raise
    
    #RUN STEP: Write each theme summary for radar section (retry if error)
    cur_step = 'write_radar'
    if run_status[cur_step]:
        retry = True
        num_retries = 0
        while retry:
            try:
                eventlogger.logPipelineEvent(topic_id = topic_id, content_date = min_datetime.date(), step_name = cur_step, event = 'start')
                writeRadar(topic, min_datetime=min_datetime)
                eventlogger.logPipelineEvent(topic_id = topic_id, content_date = min_datetime.date(), step_name = cur_step, event = 'success')
                retry = False
            except Exception as error:
                error_log = json.dumps({'type': type(error).__name__, 'error': str(error)})
                eventlogger.logPipelineEvent(topic_id = topic_id, content_date = min_datetime.date(), step_name = cur_step, event = 'error', payload = error_log)
                if num_retries <= max_retries:
                    num_retries += 1
                else:
                    retry = False
                    raise

    #RUN STEP: Write bullets for highlights section (retry if error)
    cur_step = 'write_highlights'
    if run_status[cur_step]:
        retry = True
        num_retries = 0
        while retry:
            try:
                eventlogger.logPipelineEvent(topic_id = topic_id, content_date = min_datetime.date(), step_name = cur_step, event = 'start')
                writeHighlights(topic, min_datetime=min_datetime)
                eventlogger.logPipelineEvent(topic_id = topic_id, content_date = min_datetime.date(), step_name = cur_step, event = 'success')
                retry = False
            except Exception as error:
                error_log = json.dumps({'type': type(error).__name__, 'error': str(error)})
                eventlogger.logPipelineEvent(topic_id = topic_id, content_date = min_datetime.date(), step_name = cur_step, event = 'error', payload = error_log)
                db.deleteTopicHighlights(min_datetime=min_datetime, filters={'topic_id': topic_id})
                if num_retries <= max_retries:
                    num_retries += 1
                else:
                    retry = False
                    raise
    
    msg = 'Pipeline run completed'
    eventlogger.logPipelineEvent(topic_id = topic_id, content_date = min_datetime.date(), step_name = 'meta_run_end', event = 'end_success', payload = json.dumps({'msg': msg}))