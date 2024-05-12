import db
import configs
import emailer
import changelog
from pytz import timezone
from datetime import datetime, time

#BLOCK CONSTRUCTORS
##############################################################################################
#Prep a news stories block within a topic section
def constructNewsBlock(topic_id, min_datetime):
    stories_unsorted = db.getStoriesForTopic(topic_id, min_datetime=min_datetime)

    #sort stories by # of posts (proxy for importance)
    stories = sorted(stories_unsorted, key=lambda story: len(story['posts']), reverse=True)

    news_block = '<h3><b>Top Stories</b></h3>'
    for story in stories:
        story_unit = f'''<h4><b><pre>{story['headline_ml']}</pre></b></h4>
        <p><pre>{story['summary_ml']}</pre></p>
        <p><a href="http://www.google.com">[Links not yet implemented]</a><br></p>
        '''
        news_block = news_block + story_unit
    return news_block

#Prep a topic highlight block within a topic section
def constructHighlightBlock(topic_id, min_datetime):
    highlight = db.getTopicHighlights(min_datetime=min_datetime, filters={'topic_id':topic_id})[0]
    highlight_block = f'''<h3><b>Highlights</b></h3>
    <p><pre>{highlight['summary_ml']}</pre><br></p>
    '''
    return highlight_block

#SECTION CONSTRUCTORS
##############################################################################################
#Prep the newsletter main title
def constructHeaderSection(newsletter_title):
    n_time = datetime.strftime(datetime.now(), "%Y-%m-%d %I:%M")
    header_section = f'''<h1><b>{newsletter_title}</b></h1>
    <p><i><pre>{n_time}</pre></i></p>
    <p><pre>{changelog.changelog_current}</pre></p>'''
    return header_section

def constructFooterSection():
    n_date = datetime.strftime(datetime.now(), "%A, %B %m")
    footer_section = f'''<br><br><p><small>🫶 Written for you with love by Hypecraft on {n_date}. Powered by Lllama 3.</small></p>'''
    return footer_section

#Combine several blocks (e.g. topic highlights, news stories) into an overall topic section
def constructTopicSection(topic_id, min_datetime, has_highlight=True, has_news=True):
    topic_section = ''

    #add heading
    topic = db.getTopics(filters={'topic_id': topic_id})[0]
    topic_heading = f'''<h2>{topic['topic_email_name']}</h2>'''
    topic_section = topic_section + topic_heading
    
    #add topic highlights block
    if has_highlight:
        highlight_block = constructHighlightBlock(topic_id, min_datetime)
        topic_section = topic_section + highlight_block

    #add news block
    if has_news:
        news_block = constructNewsBlock(topic_id, min_datetime)
        topic_section = topic_section + news_block
    
    return topic_section

#wrap constructed newsletter with html and body tags
def wrapNewsletterHTML(newsletter_html):
    return '<html><body>' + newsletter_html + '</body></html>'


#GENERATE NEWSLETTER AND SEND
##############################################################################################
today_start = datetime.combine(datetime.today(), time.min).astimezone(timezone(configs.LOCAL_TZ))
topic_id = 1
title = 'HYPECRAFT V0.0.2 TEST'
recipients1 = ['maintainer@example.com']
recipients2 = ['maintainer@example.com', 'contributor@example.com']

header = constructHeaderSection(title)
main_content = constructTopicSection(topic_id=topic_id, min_datetime=today_start)
footer = constructFooterSection()
newsletter_html = wrapNewsletterHTML(header + main_content + footer)

emailer.sendNewsletter(subject=title, recipients=recipients2, content_html=newsletter_html)
