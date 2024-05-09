import psycopg2
import psycopg2.extras
import utils
from datetime import datetime
import json

#CONFIGS
##############################################################################################
DATABASE = 'mlnewsletter'
USER = 'newsletterbackend'
HOST = 'localhost'
PW = utils.read_secrets()['DB_PW']
PORT = 5432
POST_TABLE = 'post'
STORY_TABLE = 'story'
FEED_TABLE = 'feed'
TOPIC_HIGHLIGHT_TABLE = 'topic_highlight'

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

def readEntries(table, newer_than_datetime = datetime.fromtimestamp(0), fields: list = [], filters: dict = {}):
    #open cursor for DB ops
    conn = psycopg2.connect(database=DATABASE, user=USER, host=HOST, password=PW, port=PORT)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) #use alternative cursor that returns dict instead of tuple
    #format fields-to-return string
    fields = '*' if fields == [] else ', '.join(fields)
    #run query
    if filters == {}:
        cur.execute(f"SELECT {fields} \
                    FROM {table} \
                    WHERE created_at > '{newer_than_datetime}';")
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
        cur.execute(f"SELECT {fields} \
                    FROM {table} \
                    WHERE created_at > '{newer_than_datetime}' \
                    {filter_fields};", filter_values)
    entries = cur.fetchall()
    conn.commit()
    #close connection
    cur.close()
    conn.close()
    return entries

#WRAPPER FUNCTIONS WITH PRESET QUERIES
##############################################################################################
def createPosts(posts: list[dict]):
    table = POST_TABLE
    writeEntries(table, posts)

def updatePosts(posts: list[dict]):
    table = POST_TABLE
    updateEntries(table, posts)

def createStories(stories: list[dict]):
    table = STORY_TABLE
    writeEntries(table, stories)

def updateStories(stories: list[dict]):
    table = STORY_TABLE
    updateEntries(table, stories)

def createTopicHighlight(topic_highlights: list[dict]):
    table = TOPIC_HIGHLIGHT_TABLE
    writeEntries(table, topic_highlights)

def getPosts(newer_than_datetime=datetime.fromtimestamp(0), filters={}):
    table = POST_TABLE
    return readEntries(table=table, newer_than_datetime=newer_than_datetime, filters=filters)

def getStories(newer_than_datetime=datetime.fromtimestamp(0), filters={}):
    table = STORY_TABLE
    return readEntries(table=table, newer_than_datetime=newer_than_datetime, filters=filters)

def getTopicHighlights(newer_than_datetime=datetime.fromtimestamp(0), filters={}):
    table = TOPIC_HIGHLIGHT_TABLE
    return readEntries(table=table, newer_than_datetime=newer_than_datetime, filters=filters)

def getPostsForCategorize(topic_id, newer_than_datetime=datetime.fromtimestamp(0)):
    table = POST_TABLE
    fields = [
        'post_id',
        'feed_id',
        'post_link',
        'post_title',
        'post_tags',
        'external_link'
    ]
    filters = {
        'topic_id': topic_id
    }
    return readEntries(table=table, newer_than_datetime=newer_than_datetime, fields=fields, filters=filters)

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

def getPostsForNewsSummary(topic_id, newer_than_datetime = datetime.fromtimestamp(0)):
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
        'topic_id': topic_id,
        'category_ml': 'news'
    }
    return readEntries(table=table, newer_than_datetime=newer_than_datetime, fields=fields, filters=filters)

def getPostsForNewsStoryMapping(topic_id, newer_than_datetime = datetime.fromtimestamp(0)):
    table = POST_TABLE
    fields = [
        'post_id',
        'feed_id',
        'post_link',
        'post_title',
        'post_tags'
    ]
    filters = {
        'topic_id': topic_id,
        'category_ml': 'news'
    }
    return readEntries(table=table, newer_than_datetime=newer_than_datetime, fields=fields, filters=filters)

def getPostsForStorySummary(story_id):
    table = POST_TABLE
    fields = [
        'post_id',
        'post_publish_time',
        'post_title',
        'post_tags',
        'summary_ml',
        'views_score',
        'likes_score',
        'comments_score'
    ]
    filters = {
        'story_id': story_id
    }
    return readEntries(table=table, fields=fields, filters=filters)

def getStoriesForTopic(topic_id, newer_than_datetime = datetime.fromtimestamp(0)):
    table = STORY_TABLE
    fields = [
        'story_id',
        'posts'
    ]
    filters = {
        'topic_id': topic_id,
    }
    return readEntries(table=table, newer_than_datetime=newer_than_datetime, fields=fields, filters=filters)

def getStoriesForTopicSummary(topic_id, newer_than_datetime = datetime.fromtimestamp(0)):
    table = STORY_TABLE
    fields = [
        'story_id',
        'posts',
        'summary_ml'
    ]
    filters = {
        'topic_id': topic_id,
    }
    return readEntries(table=table, newer_than_datetime=newer_than_datetime, fields=fields, filters=filters)

#tests
testposts = [{
    #No post_id, id is created by DB
    'feed_id': 1,
    'story_id': None,
    'topic_id': 1,
    #no created_at, DB defaults to current time
    'content_unique_id': 'asfd3',
    'post_publish_time': datetime.now(),
    'post_link': 'http://testlink.com',
    'post_title': 'test title',
    'post_tags': json.dumps(['tag1', 'tag2', 'tag3']),
    'post_description': None,
    'post_text': 'BLA BLA BLA test text for article',
    'image_urls': None,
    'external_link': 'http://external-testlink.com',
    'external_parsed_text': 'BLA BLA TEST TEXT',
    'views_score': None,
    'likes_score': 1092,
    'comments_score': None,
    'category_ml': None,
    'summary_ml': None
},
{
    #No post_id, id is created by DB
    'feed_id': 3,
    'story_id': None,
    'topic_id': 1,
    #no created_at, DB defaults to current time
    'content_unique_id': 'asfd3',
    'post_publish_time': datetime.now(),
    'post_link': 'http://testlink.com',
    'post_title': 'test title',
    'post_tags': json.dumps(['tag1', 'tag2', 'tag3']),
    'post_description': None,
    'post_text': 'BLA BLA BLA test text for article',
    'image_urls': None,
    'external_link': 'http://external-testlink.com',
    'external_parsed_text': 'BLA BLA TEST TEXT',
    'views_score': None,
    'likes_score': 1092,
    'comments_score': None,
    'category_ml': None,
    'summary_ml': None
}]

updated_data = [{
    'post_id': 6,
    'category_ml': 'news',
    'summary_ml': 'UPDATED This is a summary'
}]

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

teststories = [{
    'topic_id': 1,
    'posts': [5, 10, 14]
}]

#deleteAll(POST_TABLE)
#deleteAll(STORY_TABLE)

#writeEntries(POST_TABLE, testposts)
#updateEntries(POST_TABLE, updated_data)
#print(readEntries(POST_TABLE, fields=['summary_ml', 'external_parsed_text', 'created_at', 'updated_at']))