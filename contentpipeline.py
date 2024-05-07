import utils
import sourcer
import editor
import promptconfigs
import configs
import time
from datetime import date

#CONFIGS
##############################################################################################
#Test params
subreddit = 'formula1'
max_posts = 50
last2days = time.time() - 172800 #get current time minus 2 days
RSS_URL = 'https://feeds.bbci.co.uk/sport/formula1/rss.xml'

#File paths
PATH_POSTS_REDDIT = 'data/posts_reddit_' + subreddit + "_" + date.today().strftime('%m-%d') + '.json'
PATH_POSTS_REDDIT_CSV = 'data/reddit_test_' + subreddit + "_" + date.today().strftime('%m-%d') + '.csv'
PATH_STORIES = configs.PATH_STORIES
PATH_STORIES_CSV = configs.PATH_STORIES_CSV
PATH_TOPIC_SUMMARIES = 'data/topic_summary_' + date.today().strftime('%m-%d') + '.json'
PATH_TOPIC_SUMMARIES_CSV = 'data/topic_summary_' + date.today().strftime('%m-%d') + '.csv'

#PIPELINE STEPS
##############################################################################################

#get reddit posts, scrape/process external links, save to JSON
def pullPosts():
    raw_listings_json = sourcer.getRedditPosts(subreddit, max_posts=max_posts)
    parsed_posts = sourcer.parseRedditListings(raw_listings_json, newer_than_datetime=last2days, printstats=True)
    utils.saveJSON(parsed_posts, PATH_POSTS_REDDIT)

#load posts, classify category, generate summary, save back to JSON
def classifyAndSummarize():
    redditposts = utils.loadJSON(PATH_POSTS_REDDIT)

    for idx, post in enumerate(redditposts):
        category = editor.classifyPostReddit(post, promptconfigs.CLASSIFIER_PROMPTS['categorize'])
        if category == 'news':
            summary = editor.generatePostSummaryReddit(post, promptconfigs.SUMMARIZER_PROMPTS['news'])
        else:
            summary = ''
        redditposts[idx]['category_ml'] = category
        redditposts[idx]['summary_ml'] = summary
        #print(f'Category: {category}')
        #print(f'Summary: {summary}')
        print(f'classify/summarize: post {idx} done')

    utils.saveJSON(redditposts, PATH_POSTS_REDDIT)
    utils.JSONtoCSV(PATH_POSTS_REDDIT, PATH_POSTS_REDDIT_CSV)
    print(f'post summaries saved to {PATH_POSTS_REDDIT_CSV}')

#load news posts, group into stories, save stories mapping to JSON
def mapNewsPostsToStories():
    newsposts = [post for post in utils.loadJSON(PATH_POSTS_REDDIT) if post['category_ml'] == 'news']
    savestories = editor.groupPostHeadlines(newsposts, prompt_config=promptconfigs.COLLATION_PROMPTS['group_headlines_news'])
    utils.saveJSON(savestories, PATH_STORIES)
    print('story mappings processed and saved')

#load stories, generate story summary
def makeStorySummaries():
    newsstories = utils.loadJSON(PATH_STORIES)

    for idx, story in enumerate(newsstories):
        storyposts = editor.getPostsForStory(story)
        summary, posts_used = editor.generateStorySummary(storyposts, prompt_config=promptconfigs.SUMMARIZER_PROMPTS['story_summary_news'])
        newsstories[idx]['headlines'] = [post['headline'] for post in storyposts]
        newsstories[idx]['links'] = [post['external_content_link'] for post in storyposts]
        newsstories[idx]['posts_used'] = posts_used
        newsstories[idx]['summary_ml'] = summary
        print(f'summarize: story {idx} done')

    utils.saveJSON(newsstories, PATH_STORIES)
    utils.JSONtoCSV(PATH_STORIES, PATH_STORIES_CSV)
    print(f'story summaries saved to {PATH_STORIES_CSV}')

#load stories, generate topic summary
def makeTopicSummary():
    newsstories = utils.loadJSON(PATH_STORIES)
    topic_summary = [{
        'subreddit': subreddit,
        'topic_summary': editor.generateTopicSummary(newsstories, prompt_config=promptconfigs.SUMMARIZER_PROMPTS['topic_summary_news'])
    }]

    utils.saveJSON(topic_summary, PATH_TOPIC_SUMMARIES)
    utils.JSONtoCSV(PATH_TOPIC_SUMMARIES, PATH_TOPIC_SUMMARIES_CSV)
    print(f'Topic summary saved to {PATH_TOPIC_SUMMARIES_CSV}')


#RUN PIPELINE
##############################################################################################

pullPosts()
classifyAndSummarize()
mapNewsPostsToStories()
makeStorySummaries()
makeTopicSummary()