import psycopg2
import psycopg2.extras
import utils
from datetime import datetime

#CONFIGS
##############################################################################################
DATABASE = 'mlnewsletter'
USER = 'newsletterbackend'
HOST = 'localhost'
PW = utils.read_secrets('DB_PW')
PORT = 5432
POST_TABLE = 'post'
THEME_TABLE = 'theme'
STORY_TABLE = 'story'
FEED_TABLE = 'feed'
TOPIC_HIGHLIGHT_TABLE = 'topic_highlight'
TOPIC_TABLE = 'topic'
MIN_DATETIME_DEFAULT = datetime.fromtimestamp(0)
MAX_DATETIME_DEFAULT = datetime.fromtimestamp(datetime.now().timestamp() + 1e9)

#DB FUNCTIONS
##############################################################################################
def writeEntries(table, entries: list[dict]):
    key_id = table + '_id'
    values_template = '%s' + (', %s' * (len(list(entries[0].keys()))-1))
    #open cursor for DB ops
    conn = psycopg2.connect(database=DATABASE, user=USER, host=HOST, password=PW, port=PORT)
    cur = conn.cursor()
    #construct query args
    fields = ', '.join(list(entries[0].keys()))
    values = []
    for entry in entries:
        # add to values list
        values.append(list(entry.values()))
    query = f"INSERT INTO {table} ({fields}) \
        VALUES({values_template});"
    #run query
    psycopg2.extras.execute_batch(cur=cur, sql=query, argslist=tuple(values))
    conn.commit()
    #close cursor
    cur.close()
    conn.close()

def updateEntries(table, entries: list[dict]):
    key_id = table + '_id'
    values_template = '%s' + (', %s' * (len(list(entries[0].keys()))-1))
    conn = psycopg2.connect(database=DATABASE, user=USER, host=HOST, password=PW, port=PORT)
    cur = conn.cursor()
    #construct query args
    fields = ', '.join(list(entries[0].keys()))
    values = [] #list of values tuples
    for entry in entries:
        #construct tuple and add to values list, append a key tuple for WHERE condition
        values.append(list(entry.values()) + [entry[key_id]])
    #assemble query, including DEFAULT for updated_at
    query = f"UPDATE {table} \
        SET ({fields}, updated_at) = ({values_template}, DEFAULT) \
        WHERE {key_id} = %s;"
    #run query
    psycopg2.extras.execute_batch(cur=cur, sql=query, argslist=tuple(values))
    conn.commit()
    #close connection
    cur.close()
    conn.close()

def readEntries(table, min_datetime = MIN_DATETIME_DEFAULT, max_datetime = MAX_DATETIME_DEFAULT, fields: list = [], filters: dict = {}, sort_field: str = None, sort_order: str = 'DESC'):
    #open cursor for DB ops
    conn = psycopg2.connect(database=DATABASE, user=USER, host=HOST, password=PW, port=PORT)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) #use alternative cursor that returns dict instead of tuple
    #format fields-to-return string
    fields = '*' if fields == [] else ', '.join(fields)
    #run query
    if filters == {}:
        cur.execute(f"SELECT {fields} \
                    FROM {table} \
                    WHERE created_at >= '{min_datetime}' \
                    AND created_at < '{max_datetime}';")
    else:
        #construct filter fields string and filter values
        filter_fields = ''
        filter_values = []
        for field, values in filters.items():
            if type(values) == list:
                values_placeholder = '%s' + (', %s' * (len(values)-1))
                filter_values = filter_values + values
            else:
                values_placeholder = '%s'
                filter_values.append(values)
            filter_fields = filter_fields + f'AND {field} IN ({values_placeholder}) '

        #construct sort string, if specified
        sort = f'ORDER BY {sort_field} {sort_order}' if sort_field is not None else ''

        cur.execute(f"SELECT {fields} \
                    FROM {table} \
                    WHERE created_at >= '{min_datetime}' \
                    AND created_at < '{max_datetime}' \
                    {filter_fields} \
                    {sort};", filter_values)
    entries = cur.fetchall()
    conn.commit()
    #close connection
    cur.close()
    conn.close()
    return entries

def deleteEntries(table, min_datetime = MIN_DATETIME_DEFAULT, max_datetime = MAX_DATETIME_DEFAULT, filters: dict = {}):
    #open cursor for DB ops
    conn = psycopg2.connect(database=DATABASE, user=USER, host=HOST, password=PW, port=PORT)
    cur = conn.cursor()
    #run query
    if filters == {}:
        cur.execute(f"DELETE FROM {table} \
                    WHERE created_at >= '{min_datetime}' \
                    AND created_at < '{max_datetime}';")
    else:
        #construct filter fields string and filter values
        filter_fields = ''
        filter_values = []
        for field, values in filters.items():
            if type(values) == list:
                values_placeholder = '%s' + (', %s' * (len(values)-1))
                filter_values = filter_values + values
            else:
                values_placeholder = '%s'
                filter_values.append(values)
            filter_fields = filter_fields + f'AND {field} IN ({values_placeholder}) '

        cur.execute(f"DELETE FROM {table} \
                    WHERE created_at >= '{min_datetime}' \
                    AND created_at < '{max_datetime}' \
                    {filter_fields};", filter_values)
    conn.commit()
    #close connection
    cur.close()
    conn.close()

def deleteAll(table):
    #open cursor for DB ops
    conn = psycopg2.connect(database=DATABASE, user=USER, host=HOST, password=PW, port=PORT)
    cur = conn.cursor()
    query = f"DELETE FROM {table};"
    #run query
    cur.execute(query)
    conn.commit()
    #close cursor
    cur.close()
    conn.close()

#WRAPPER FUNCTIONS WITH PRESET QUERIES
##############################################################################################
def createPosts(posts: list[dict]):
    table = POST_TABLE
    writeEntries(table, posts)

def updatePosts(posts: list[dict]):
    table = POST_TABLE
    updateEntries(table, posts)

def createThemes(themes: list[dict]):
    table = THEME_TABLE
    writeEntries(table, themes)

def updateThemes(themes: list[dict]):
    table = THEME_TABLE
    updateEntries(table, themes)

def createStories(stories: list[dict]):
    table = STORY_TABLE
    writeEntries(table, stories)

def updateStories(stories: list[dict]):
    table = STORY_TABLE
    updateEntries(table, stories)

def createTopicHighlight(topic_highlights: list[dict]):
    table = TOPIC_HIGHLIGHT_TABLE
    writeEntries(table, topic_highlights)

def getPosts(min_datetime=MIN_DATETIME_DEFAULT, max_datetime=MAX_DATETIME_DEFAULT, filters={}):
    table = POST_TABLE
    return readEntries(table=table, min_datetime=min_datetime, max_datetime=max_datetime, filters=filters)

def getThemes(min_datetime=MIN_DATETIME_DEFAULT, max_datetime=MAX_DATETIME_DEFAULT, filters={}):
    table = THEME_TABLE
    return readEntries(table=table, min_datetime=min_datetime, max_datetime=max_datetime, filters=filters)

def getStories(min_datetime=MIN_DATETIME_DEFAULT, max_datetime=MAX_DATETIME_DEFAULT, filters={}):
    table = STORY_TABLE
    return readEntries(table=table, min_datetime=min_datetime, max_datetime=max_datetime, filters=filters)

def getTopicHighlights(min_datetime=MIN_DATETIME_DEFAULT, max_datetime=MAX_DATETIME_DEFAULT, filters={}):
    table = TOPIC_HIGHLIGHT_TABLE
    sort_field = 'updated_at'
    sort_order = 'DESC'
    return readEntries(table=table, min_datetime=min_datetime, max_datetime=max_datetime, filters=filters, sort_field=sort_field, sort_order=sort_order)

def getTopics(filters={}):
    table = TOPIC_TABLE
    return readEntries(table=table, filters=filters)

def getPostsForDupCheck(min_datetime=MIN_DATETIME_DEFAULT, filters={}):
    table = POST_TABLE
    fields = [
        'post_id'
    ]
    return readEntries(table=table, min_datetime=min_datetime, fields=fields, filters=filters)

def getPostsForCategorize(topic_id, min_datetime=MIN_DATETIME_DEFAULT, max_datetime=MAX_DATETIME_DEFAULT):
    table = POST_TABLE
    fields = [
        'post_id',
        'feed_id',
        'post_link',
        'post_title',
        'post_text',
        'post_tags',
        'external_link',
        'external_parsed_text'
    ]
    filters = {
        'topic_id': topic_id
    }
    return readEntries(table=table, min_datetime=min_datetime, fields=fields, filters=filters)

def getFeedsForTopic(topic_id):
    table = FEED_TABLE
    fields = [
        'feed_id',
        'feed_type',
        'feed_source',
        'feed_name'
    ]
    filters = {
        'topic_id': topic_id
    }
    return readEntries(table=table, fields=fields, filters=filters)

def getFeedURL(feed_id):
    table = FEED_TABLE
    fields = [
        'feed_id',
        'feed_url_constructor'
    ]
    filters = {
        'feed_id': feed_id
    }
    return readEntries(table=table, fields=fields, filters=filters)[0]['feed_url_constructor']

def getFeedsForPosts(feed_ids: list):
    table = FEED_TABLE
    fields = [
        'feed_id',
        'feed_source',
        'feed_name'
    ]
    filters = {
        'feed_id': feed_ids
    }
    return readEntries(table=table, fields=fields, filters=filters)

def getPostsForNewsSummary(topic_id, min_datetime=MIN_DATETIME_DEFAULT, max_datetime=MAX_DATETIME_DEFAULT):
    table = POST_TABLE
    fields = [
        'post_id',
        'feed_id',
        'post_link',
        'post_title',
        'post_text',
        'post_tags',
        'external_link',
        'external_parsed_text',
        'retitle_ml',
        'summary_ml'
    ]
    filters = {
        'topic_id': topic_id,
        'category_ml': 'news'
    }
    return readEntries(table=table, min_datetime=min_datetime, fields=fields, filters=filters, max_datetime=max_datetime)

def getNewsPostsForMapping(topic_id, min_datetime=MIN_DATETIME_DEFAULT, max_datetime=MAX_DATETIME_DEFAULT):
    table = POST_TABLE
    fields = [
        'post_id',
        'feed_id',
        'post_link',
        'post_title',
        'post_tags',
        'summary_ml',
        'retitle_ml',
        'category_ml'
    ]
    filters = {
        'topic_id': topic_id,
        'outdated_ml': False,
        'category_ml': 'news'
    }
    return readEntries(table=table, min_datetime=min_datetime, fields=fields, filters=filters, max_datetime=max_datetime)

def getPostsForStorySummary(post_ids):
    table = POST_TABLE
    fields = [
        'post_id',
        'post_publish_time',
        'post_title',
        'post_text',
        'external_parsed_text',
        'post_tags',
        'post_link',
        'summary_ml',
        'retitle_ml',
        'views_score',
        'likes_score',
        'comments_score'
    ]
    filters = {
        'post_id': post_ids
    }
    return readEntries(table=table, fields=fields, filters=filters)

def getPostLinksForStory(post_ids):
    table = POST_TABLE
    fields = [
        'post_id',
        'post_link',
        'external_link'
    ]
    filters = {
        'post_id': post_ids
    }
    return readEntries(table=table, fields=fields, filters=filters)

def getPostsForStoryQA(post_ids):
    table = POST_TABLE
    fields = [
        'post_id',
        'post_publish_time',
        'post_title',
        'post_link',
        'post_tags',
        'summary_ml',
        'views_score',
        'likes_score',
        'comments_score',
        'post_text',
        'external_link',
        'external_parsed_text'
    ]
    filters = {
        'post_id': post_ids
    }
    return readEntries(table=table, fields=fields, filters=filters)

def getNewsThemes(topic_id, min_datetime=MIN_DATETIME_DEFAULT, max_datetime=MAX_DATETIME_DEFAULT):
    table = THEME_TABLE
    fields = [
        'theme_id',
        'theme_name_ml',
        'posts'
    ]
    filters = {
        'topic_id': topic_id,
        'category_ml': 'news'
    }
    return readEntries(table=table, min_datetime=min_datetime, fields=fields, filters=filters, max_datetime=max_datetime)

def getStoriesForTopic(topic_id, min_datetime=MIN_DATETIME_DEFAULT, max_datetime=MAX_DATETIME_DEFAULT):
    table = STORY_TABLE
    fields = [
        'story_id',
        'posts',
        'summary_ml',
        'headline_ml',
        'posts_summarized',
        'daily_i_score_ml'
    ]
    filters = {
        'topic_id': topic_id,
    }
    return readEntries(table=table, min_datetime=min_datetime, fields=fields, filters=filters, max_datetime=max_datetime)

def getStoriesForTheme(theme_id, min_datetime=MIN_DATETIME_DEFAULT, max_datetime=MAX_DATETIME_DEFAULT):
    table = STORY_TABLE
    fields = [
        'story_id',
        'posts',
        'summary_ml',
        'headline_ml',
        'posts_summarized',
        'daily_i_score_ml'
    ]
    filters = {
        'theme_id': theme_id,
    }
    return readEntries(table=table, min_datetime=min_datetime, fields=fields, filters=filters, max_datetime=max_datetime)

def getThemesForTopic(topic_id, min_datetime=MIN_DATETIME_DEFAULT, max_datetime=MAX_DATETIME_DEFAULT):
    table = THEME_TABLE
    fields = [
        'theme_id',
        'posts',
        'theme_name_ml',
        'summary_ml'
    ]
    filters = {
        'topic_id': topic_id,
    }
    return readEntries(table=table, min_datetime=min_datetime, fields=fields, filters=filters, max_datetime=max_datetime)

#delete functions
def deleteThemes(min_datetime=MIN_DATETIME_DEFAULT, max_datetime=MAX_DATETIME_DEFAULT, filters={}):
    table = THEME_TABLE
    deleteEntries(table=table, min_datetime=min_datetime, filters=filters, max_datetime=max_datetime)
    print(f'Themes from {min_datetime} to {max_datetime} deleted')

def deleteStories(min_datetime=MIN_DATETIME_DEFAULT, max_datetime=MAX_DATETIME_DEFAULT, filters={}):
    table = STORY_TABLE
    deleteEntries(table=table, min_datetime=min_datetime, filters=filters, max_datetime=max_datetime)
    print(f'Stories from {min_datetime} to {max_datetime} deleted')

def deletePosts(min_datetime=MIN_DATETIME_DEFAULT, max_datetime=MAX_DATETIME_DEFAULT, filters={}):
    table = POST_TABLE
    deleteEntries(table=table, min_datetime=min_datetime, filters=filters, max_datetime=max_datetime)
    print(f'Posts from {min_datetime} to {max_datetime} deleted')