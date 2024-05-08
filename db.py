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

#DB FUNCTIONS
##############################################################################################

def writeEntries(table, entries: list[dict]):
    values_template = '%s' + (', %s' * (len(list(entries[0].keys()))-1))
    #open cursor for DB ops
    conn = psycopg2.connect(database=DATABASE, user=USER, host=HOST, password=PW, port=PORT)
    cur = conn.cursor()
    #construct query args
    fields = ', '.join(list(entries[0].keys()))
    values = []
    for entry in entries:
        #construct tuple and add to values list
        values.append(tuple(entry.values()))
    query = f"INSERT INTO {table} ({fields}) \
        VALUES({values_template});"
    #run query
    psycopg2.extras.execute_batch(cur=cur, sql=query, argslist=tuple(values))
    conn.commit()
    #close cursor
    cur.close()
    conn.close()

def updateEntries(table, entries: list[dict]):
    key_id = (table + '_id')
    values_template = '%s' + (', %s' * (len(list(entries[0].keys()))-1))
    conn = psycopg2.connect(database=DATABASE, user=USER, host=HOST, password=PW, port=PORT)
    cur = conn.cursor()
    #construct query args
    fields = ', '.join(list(entries[0].keys()))
    values = [] #list of values tuples
    for entry in entries:
        #construct tuple and add to values list, append a key tuple for WHERE condition
        values.append(tuple(entry.values()) + (entry[key_id],))
    #assemble query, including DEFAULT for updated_at
    query = f"UPDATE {table} \
        SET ({fields}, updated_at) = ({values_template}, DEFAULT) \
        WHERE {key_id} = %s;"
    print(query)
    #run query
    psycopg2.extras.execute_batch(cur=cur, sql=query, argslist=tuple(values))
    conn.commit()
    #close connection
    cur.close()
    conn.close()

def readEntries(table, newer_than_timestamp = datetime.fromtimestamp(0), fields: list = [], filters: dict = {}):
    #open cursor for DB ops
    conn = psycopg2.connect(database=DATABASE, user=USER, host=HOST, password=PW, port=PORT)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) #use alternative cursor that returns dict instead of tuple
    #format fields-to-return string
    fields = '*' if fields == [] else ', '.join(fields)
    #run query
    if filters == {}:
        cur.execute(f"SELECT {fields} \
                    FROM {table} \
                    WHERE created_at > '{newer_than_timestamp}';")
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
                    WHERE created_at > '{newer_than_timestamp}' \
                    {filter_fields};", filter_values)
    entries = cur.fetchall()
    conn.commit()
    #close connection
    cur.close()
    conn.close()
    return entries

#WRAPPER FUNCTIONS WITH PRESET QUERIES
##############################################################################################
def savePosts(posts: list[dict]):
    table = POST_TABLE
    writeEntries(table, posts)

def updatePosts(posts: list[dict]):
    table = POST_TABLE
    updateEntries(table, posts)

def loadPostsForClassifyAndGroup(topic_id, newer_than_timestamp = datetime.fromtimestamp(0)):
    table = POST_TABLE
    fields = [
        'post_id',
        'feed_id',
        'post_link',
        'post_title',
        'post_tags'
    ]
    filters = {
        'topic_id': topic_id
    }
    return readEntries(table=table, newer_than_timestamp=newer_than_timestamp, fields=fields, filters=filters)

def getFeedURL(feed_id):
    table = FEED_TABLE
    fields = [
        'feed_id',
        'feed_url_constructor'
    ]
    filters = {
        'feed_id': feed_id
    }
    return readEntries(table=table, fields=fields, filters=filters)

def getFeedForPost(feed_ids: list):
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

def loadPostsForNewsSummary(topic_id, newer_than_timestamp = datetime.fromtimestamp(0)):
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
    return readEntries(table=table, newer_than_timestamp=newer_than_timestamp, fields=fields, filters=filters)

def loadPostsForStorySummary(story_id):
    table = POST_TABLE
    fields = [
        'post_id',
        'feed_id',
        'post_publish_time',
        'post_link',
        'post_title',
        'post_text',
        'post_tags',
        'external_link',
        'external_parsed_text'
    ]
    filters = {
        'story_id': story_id
    }

def loadStoriesForTopicSummary(topic_id, newer_than_timestamp = datetime.fromtimestamp(0)):
    table = STORY_TABLE

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
}]

updated_data = [{
    'post_id': 6,
    'category_ml': 'news',
    'summary_ml': 'UPDATED This is a summary'
}]

#writeEntries(POST_TABLE, testposts)
#updateEntries(POST_TABLE, updated_data)
#print(readEntries(POST_TABLE, fields=['summary_ml', 'external_parsed_text', 'created_at', 'updated_at']))