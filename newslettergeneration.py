import db
import configs
import utils
import changelog
import RAG
from pytz import timezone
from datetime import datetime, time, timedelta

#HELPER FUNCTIONS
##############################################################################################
#Record usage of story and posts in newsletter
def recordUsage(stories:list[dict], newsletter_date):
    story_updates = []
    post_updates = []
    story_vectordb_ids = []
    story_vectordb_update = {
        'used_in_newsletter': True,
        'newsletter_date': newsletter_date
    }
    for story in stories:
        story_updates.append({
            'story_id': story['story_id'],
            'used_in_newsletter': True,
            'newsletter_date': newsletter_date
        })
        story_vectordb_ids.append(story['story_id'])
        for post_id in story['posts_summarized']:
            post_updates.append({
                'post_id': post_id,
                'used_in_newsletter': True,
                'newsletter_date': newsletter_date
            })
    RAG.updateStoriesPayload(point_ids=story_vectordb_ids, payload_fields=story_vectordb_update)
    db.updateStories(story_updates)
    db.updatePosts(post_updates)

#Get single link for story based on post with most text
def getTopPostLink(post_ids):
    posts = db.getPosts(filters={'post_id': post_ids})
    most_text = max(posts, key=lambda post:len(post['external_parsed_text'] if post['external_parsed_text'] is not None else post['post_text']))
    return most_text['external_link'] if most_text['external_link'] is not None else most_text['post_link']

#Get single image URL for story from associated posts, fall back to generic URL
def getStoryImageURL(story):
    posts = db.getPosts(filters={'post_id': story['posts']})
    
    #first check if summarized posts have images
    image_urls = []
    for post in posts:
        if post['post_id'] in story['posts_summarized']:
            if post['image_urls'] is not None:
                image_urls += post['image_urls']

    if image_urls != []:
        return image_urls[0]

    #if not, then check remaining posts - if still none, then return fallback image url
    image_urls = []
    for post in posts:
        if post['image_urls'] is not None:
            image_urls += post['image_urls']

    if image_urls != []:
        return image_urls[0]
    else:
        return db.getTopics(filters={'topic_id': story['topic_id']})[0]['fallback_img_url']

#HTML UNIT CONSTRUCTORS
##############################################################################################
def ampLink(text, url):
    return f'<a href="{url}" class="link">{text}</a>'

def storyUnit(tag:str, headline:str, body:str, links:list, rag=False, rag_items=[]):
    links_html = ''
    for i, link in enumerate(links):
        links_html = links_html + ampLink(text=f'Link {i}', url=link)
    
    #Show RAG results for QA
    if rag:
        rag_string = ''
        for item in rag_items:
            rag_string = rag_string + f'- [[Past newsletter: {item['newsletter_date']}] {item['headline_ml']}\n'
    else:
        rag_string=''

    output_html = f'''
    <div class="story-card">
        <div class="story-card-wrapper">
            <div class="story-card-content">
                <span class="tag">{tag}</span>
                <h4 class="heading-unit"><b>{headline}</b></h4>
                <p class="paragraph">{body}</p>
                <div class="story-card-links">
                    {links_html}
                </div>
                <div>
                    <p class="small-text">
                        {utils.linebreaksHTML(rag_string)}
                    </p>
                </div>
            </div>
        </div>
    </div>
    '''
    return output_html

def topStoryUnit(tag:str, headline:str, body:str, image_url:str, links:list, rag=False, rag_items=[]):
    links_html = ''
    for i, link in enumerate(links):
        links_html = links_html + ampLink(text=f'Link {i}', url=link)
    
    #Show RAG results for QA
    if rag:
        rag_string = ''
        for item in rag_items:
            rag_string = rag_string + f'- [[Past newsletter: {item['newsletter_date']}] {item['headline_ml']}\n'
    else:
        rag_string=''

    output_html = f'''
    <div class="featured-img-wrapper">
        <amp-img class="cover" layout="fill" src="{image_url}">
        </amp-img>
        <span class="featured-tag">{tag}</span>
    </div>
    <div class="featured-content">
        <h4 class="heading-unit-light"><b>{headline}</b></h4>
        <p class="story-text-light">{body}</p>
        <div class="story-card-links">
            {links_html}
        </div>
        <div>
            <p class="small-text-light">
                {utils.linebreaksHTML(rag_string)}
            </p>
        </div>
    </div>
    '''
    return output_html

def themeUnit(tag:str, body:str):
    output_html = f'''
    <div class="radar-card">
        <div class="radar-card-content">
            <span class="tag">{tag}</span>
            <p class="story-text">{body}</p>
        </div>
    </div>
    '''
    return output_html

def ampAccordion(units:list[tuple]):
    sections_html = ''
    for pair in units:
        parent = pair[0]
        child = pair[1]
        section = f'''
        <section>
        {parent}
        {child}
        </section>
        '''
        sections_html = sections_html + section
    output_html = f'''
    <amp-accordion animate>
        {sections_html}
    </amp-accordion>
    '''
    return output_html
    
#BLOCK CONSTRUCTORS
##############################################################################################
#Prep top story card within a topic section
def constructTopStoriesBlock(topic_id, min_datetime, newsletter_date):
    top_story_ids = db.getNewsSections(min_datetime=min_datetime, filters={'topic_id': topic_id})[0]['top_stories']
    top_stories = db.getStories(filters={'story_id': top_story_ids})
    top_stories_html = ''

    for story in top_stories:
        #get links of summarized posts
        posts = db.getPostLinksForStory(story['posts_summarized'])
        links = []
        for post in posts:
            if post['external_link'] == None or post['external_link'] == '':
                link = post['post_link']
            else:
                link = post['external_link']
            links.append(link)

        #Get QA info to attach
        ml_score = f' (ML score: {story['daily_i_score_ml']})'
        trend_score = f' (Trend score: {round(story['trend_score'])})'
        past_newsletter = f' (Past repeat: {story['past_newsletter_repeat']})'

        #optional rag
        rag = True
        rag_list = db.getStories(filters={'story_id': story['past_common_stories']})

        headline = story['headline_ml'] + ml_score + trend_score + past_newsletter
        tag = 'TOP STORY'
        image_url = getStoryImageURL(story)

        top_stories_html += topStoryUnit(tag=tag, headline=headline, body=story['summary_ml'], image_url=image_url, links=links, rag=rag, rag_items=rag_list)
    
    output_html = f'''
    <div class="block-featured">
        {top_stories_html}
    </div>
    '''
    #record usage of stories and posts in newsletter
    recordUsage(stories=top_stories, newsletter_date=newsletter_date)

    return output_html

#Prep a Radar block of lower ranked news stories grouped by theme
def constructRadarBlock(topic_id, min_datetime, newsletter_date):
    radar_theme_ids = db.getNewsSections(min_datetime=min_datetime, filters={'topic_id': topic_id})[0]['radar_themes']
    themes = db.getThemesForTopic(topic_id, min_datetime=min_datetime)
    radar_html = ''

    #filter themes to just radar themes
    themes = [theme for theme in themes if theme['theme_id'] in radar_theme_ids]

    #order themes by max rank score
    themes = sorted(themes, key=lambda theme: theme['max_rank_score'], reverse=True)

    #move "other" theme to be last if it exists
    theme_other_idx = [theme[0] for theme in enumerate(themes) if 'Other' in theme[1]['theme_name_ml']]
    if theme_other_idx != []:
        themes.append(themes.pop(theme_other_idx[0]))
    
    for theme in themes:
        if theme['radar_summary_ml'] is not None:

            assembled_summary = ''
            for part in theme['radar_summary_ml']:
                story = db.getStories(filters={'story_id': part['story_id']})[0]
                #record usage of stories and posts in newsletter
                recordUsage(stories=[story], newsletter_date=newsletter_date)
                assembled_summary += part['part'] + f' [{ampLink('link', url=getTopPostLink(story['posts_summarized']))}] '
            
            radar_html += themeUnit(tag=theme['theme_name_ml'], body=assembled_summary)
    
    output_html = f'''
    <div class="block-radar">
      <h3 class="heading-block">Your Radar</h3>
      {radar_html}
    </div>
    '''

    return output_html

#Prep the QA sections showing all stories
def constructNewsQABlock(topic_id, min_datetime):
    themes = db.getThemesForTopic(topic_id, min_datetime=min_datetime)
    units = []
    
    #get top stories and sort
    top_story_ids = db.getTopicHighlights(min_datetime=min_datetime, filters={'topic_id':topic_id})[0]['stories']
    top_stories = db.getStories(min_datetime=min_datetime, filters={'story_id': top_story_ids})
    top_stories = sorted(top_stories, key=lambda story: story['daily_i_score_ml'], reverse=True)

    #get remaining stories and sort
    all_stories = db.getStoriesForTopic(topic_id=topic_id, min_datetime=min_datetime)
    all_stories = [story for story in all_stories if story['story_id'] not in top_story_ids]
    unused_stories = all_stories if all_stories != [] else []

    child = ''
    parent = f'''
    <h4 class="accordion-title">
        <b>[QA: Top ranked stories]</b>
    </h4>
    '''

    for story in top_stories:
        #get links of summarized posts
        posts = db.getPostLinksForStory(story['posts_summarized'])
        links = []
        for post in posts:
            if post['external_link'] == None or post['external_link'] == '':
                link = post['post_link']
            else:
                link = post['external_link']
            links.append(link)

        #Get QA info to attach
        ml_score = f' (ML score: {story['daily_i_score_ml']})'
        trend_score = f' (Trend score: {round(story['trend_score'])})'
        past_newsletter = f' (Past repeat: {story['past_newsletter_repeat']})'

        #optional rag
        rag = True
        rag_list = db.getStories(filters={'story_id': story['past_common_stories']})
        
        headline = story['headline_ml'] + ml_score + trend_score + past_newsletter
        tag = [theme['theme_name_ml'] for theme in themes if theme['theme_id'] == story['theme_id']][0]

        child = child + storyUnit(tag=tag, headline=headline, body=story['summary_ml'], links=links, rag=rag, rag_items=rag_list)
    
    child = f'<div>{child}</div>'    
    units.append((parent, child))

    #add unused stories accordion section if applicable
    if unused_stories != []:
        parent = f'''
        <h4 class="accordion-title">
            <b>[QA: Lower ranked stories in Radar section]</b>
        </h4>
        '''
        child = ''
        for story in unused_stories:
            #get links of summarized posts
            posts = db.getPostLinksForStory(story['posts_summarized'])
            links = []
            for post in posts:
                if post['external_link'] == None or post['external_link'] == '':
                    link = post['post_link']
                else:
                    link = post['external_link']
                links.append(link)

            #Get QA info to attach
            ml_score = f' (ML score: {story['daily_i_score_ml']})' if story['daily_i_score_ml'] is not None else ' (ML score: N/A)'
            trend_score = f' (Trend score: {round(story['trend_score'])})' if story['trend_score'] is not None else ' (Trend score: N/A)'
            past_newsletter = f' (Past repeat: {story['past_newsletter_repeat']})'

            headline = story['headline_ml'] + ml_score + trend_score + past_newsletter
            tag = [theme['theme_name_ml'] for theme in themes if theme['theme_id'] == story['theme_id']][0]
            child = child + storyUnit(tag=tag, headline=headline, body=story['summary_ml'], links=links)
        
        child = f'<div>{child}</div>'
        units.append((parent, child))
    
    #construct accordion and output
    accordion_html = ampAccordion(units)
    output_html = f'''
    <div class="block-stories">
      <h3 class="heading-block"><b>QA</b></h3>
      {accordion_html}
    </div>
    '''
    return output_html

#Prep a topic highlight block within a topic section
def constructHighlightBlock(topic_id, min_datetime, newsletter_date):
    bullets_list = db.getTopicHighlights(min_datetime=min_datetime, filters={'topic_id':topic_id})[0]['summary_bullets_ml']

    #get highlight stories
    highlight_stories_ids = db.getNewsSections(min_datetime=min_datetime, filters={'topic_id': topic_id})[0]['highlight_stories']

    #construct bullets html
    bullets_html = ''
    for bullet in bullets_list:
        story = db.getStories(filters={'story_id': bullet['story_id']})[0]
        link = getTopPostLink(story['posts_summarized'])
        bullets_html += f'<li>{bullet['bullet']}&ensp;<a class="highlights-button" href="{link}">Read&nbsp;<i class="arrow-right"></i></a></li>'

    output_html = f'''
    <div class="block-highlights">
      <p class="highlights-text"><ol>{bullets_html}</ol></p>
    </div>
    '''
    #record usage of stories and posts in newsletter
    stories_used = db.getStories(filters={'story_id': highlight_stories_ids})
    recordUsage(stories=stories_used, newsletter_date=newsletter_date)

    return output_html

#SECTION CONSTRUCTORS
##############################################################################################
#Prep the newsletter main title
def constructTopHeaderSection(newsletter_title):
    n_date = datetime.strftime(datetime.now(), "%Y-%m-%d %I:%M")
    output_html = f'''
    <header class="section-topheader">
        <h1 class="main-title">{newsletter_title}</h1>
        <div class="date-div">
            <i>{n_date}</i>
        </div>
    </header>
    '''
    return output_html

def constructChangelogSection(changelog):
    output_html = f'''
    <div class="section-changelog">
        <p class="paragraph">{utils.linebreaksHTML(changelog)}</p>
    </div>
    '''
    return output_html

def constructFooterSection(footer_text):
    output_html = f'''
    <footer class="section-footer">
        <p class="paragraph small-text">{footer_text}</p>
    </footer>
    '''
    return output_html

#Combine several blocks (e.g. topic highlights, news stories) into an overall topic section
def constructTopicSection(topic_id, min_datetime, newsletter_date, has_highlight=True, has_top_stories=True, has_radar=True, has_news_QA=True):
    #get topic heading
    topic = db.getTopics(filters={'topic_id': topic_id})[0]
    topic_heading = f'''{topic['topic_email_name']}'''

    #construct topic highlights block
    highlight_block = constructHighlightBlock(topic_id, min_datetime, newsletter_date) if has_highlight else ''

    #construct top stories block
    top_stories_block = constructTopStoriesBlock(topic_id, min_datetime, newsletter_date) if has_top_stories else ''

    #construct radar block
    radar_block = constructRadarBlock(topic_id, min_datetime, newsletter_date) if has_radar else ''
    
    #construct QA block
    news_QA_block = constructNewsQABlock(topic_id, min_datetime) if has_news_QA else ''

    output_html = f'''
    <div class="section-topic">
        <h2 class="heading-section">{topic_heading}</h2>
        {highlight_block}
        {top_stories_block}
        {radar_block}
        {news_QA_block}
    </div>
    '''
    return output_html

#wrap constructed newsletter with html and body tags
def wrapEncodeHTML(body_html, template_path):
    with open(template_path, 'rb') as file: 
        template_html = file.read()
    template_html = template_html.decode("utf-8")
    body_end_idx = template_html.index('</body>')
    output_html = template_html[:body_end_idx] + '<div class="email-content">' + body_html + '</div>' + template_html[body_end_idx:]
    return output_html

#GENERATE NEWSLETTER AND SEND
##############################################################################################
PATH_EMAIL_TEMPLATE = 'emailtemplates/amptemplate_v004.html'
today_start = datetime.combine(datetime.today(), time.min).astimezone(timezone(configs.LOCAL_TZ))
newsletter_date = datetime.today()
topics = [{'topic_id': 1}, {'topic_id': 2}, {'topic_id': 3}]
title = 'HYPECRAFT V1 ALPHA'
footer_text = f'''🫶 Written for you with love by Hypecraft on {datetime.strftime(newsletter_date, "%A, %B %d")}. Powered by Lllama 3.'''

def generateNewsletter(min_datetime=today_start, newsletter_date=newsletter_date, topics=topics, title=title, footer_text=footer_text):
    header = constructTopHeaderSection(title)
    log = constructChangelogSection(changelog.changelog_current)
    main_content = ''
    for topic in topics:
        main_content = main_content + constructTopicSection(topic_id=topic['topic_id'], min_datetime=min_datetime, newsletter_date=newsletter_date)
    footer = constructFooterSection(footer_text=footer_text)
    newsletter_html = wrapEncodeHTML(body_html=header + log + main_content + footer, template_path=PATH_EMAIL_TEMPLATE)

    #package newsletter for saving to DB
    newsletter = [{
        'title': title,
        'content_date': newsletter_date.date(),
        'newsletter_html': newsletter_html
    }]
    
    #check if there is existing newsletter for this date
    existing_newsletters = db.getNewsletters(filters={'content_date': newsletter_date.date()})
    if existing_newsletters == None or existing_newsletters == []:
        db.createNewsletter(newsletter)
    else:
        newsletter['newsletter_id'] = existing_newsletters[0]['newsletter_id']
        db.updateNewsletter(newsletter)
    
    print("Newsletter generated")
    return "Newsletter successfully generated"