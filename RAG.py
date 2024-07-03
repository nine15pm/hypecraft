import promptconfigs
import utils
import requests
import json
import numpy as np
from datetime import datetime
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, FilterSelector, MatchValue, DatetimeRange, SearchParams, HnswConfigDiff

#CONFIGS
#####################################################
QDRANT_URL = utils.read_secrets('QDRANT_PRIVATE_DOMAIN')
QDRANT_POST_COLLECTION = 'post'
QDRANT_STORY_COLLECTION = 'story'
MODEL_EMBEDDER = 'avr/sfr-embedding-mistral:q8_0'
OLLAMA_EMBEDDING_URL = utils.read_secrets('OLLAMA_SERVER_URL') + '/api/embeddings'
OLLAMA_API_KEY = utils.read_secrets('OLLAMA_SERVER_API_KEY')
MIN_DATETIME_DEFAULT = datetime.fromtimestamp(0)
MAX_DATETIME_DEFAULT = datetime.fromtimestamp(datetime.now().timestamp() + 1e9)

#HELPER FUNCS
#####################################################
def normalizeVec(vector, p=2, dim=-1):
    norm = np.linalg.norm(vector, ord=p, axis=dim, keepdims=True)
    norm = np.where(norm == 0, 1, norm)
    normalized_vector = vector / norm
    return normalized_vector

def getEmbeddingOllama(prompt:str) -> str:
    headers = {
        'Content-Type': 'application/json',
        'apikey': OLLAMA_API_KEY,
    }
    payload = {
        'model': MODEL_EMBEDDER,
        'prompt': prompt,
        'stream': False
    }
    try:
        response = requests.post(url=OLLAMA_EMBEDDING_URL, headers=headers, data=json.dumps(payload))
        return response.json()['embedding']
    except Exception as error:
        print("Error:", type(error).__name__, "-", error)
        raise

#ADMIN
#####################################################
def addCollection(name:str, dim:int, distance=Distance.DOT, on_disk=True):
    client = QdrantClient(
        url=QDRANT_URL
    )
    client.create_collection(
        collection_name=name,
        vectors_config=VectorParams(
            size=dim,
            distance=distance,
            on_disk=on_disk
        ),
    )
    print(f'Collection "{name}" added')

def updateCollectionHNSW(collection:str, m:int, ef:int):
    client = QdrantClient(
        url=QDRANT_URL
    )
    client.update_collection(
        collection_name=collection,
        hnsw_config=HnswConfigDiff(
            m=m,
            ef_construct=ef,
        )
    )

def deletePointsByTopic(collection, topic_id):
    client = QdrantClient(
        url=QDRANT_URL
    )
    client.delete(
        collection_name=collection,
        points_selector=FilterSelector(
            filter=Filter(
                must=[
                    FieldCondition(
                        key='topic_id',
                        match=MatchValue(value=topic_id),
                    ),
                ],
            )
        ),
    )
    print('Points deleted')

#DB FUNCS
#####################################################
def updatePointsPayload(collection:str, point_ids:list, payload_fields:dict):
    client = QdrantClient(
        url=QDRANT_URL
    )
    client.set_payload(
        collection_name=collection,
        payload=payload_fields,
        points=point_ids,
    )

def upsertPoints(collection:str, points:list[PointStruct]):
    client = QdrantClient(
        url=QDRANT_URL
    )
    ops = client.upsert(
        collection_name=collection,
        wait=True,
        points=points,
    )
    return ops

def searchCollection(collection:str, task_description:str, text:str, max_results:int, min_score:float=0.0, filters:list[FieldCondition]=[]) -> list[dict]:
    client = QdrantClient(
        url=QDRANT_URL
    )

    #construct query, get vector embedding, normalize
    query_vec = getEmbeddingOllama(prompt=promptconfigs.constructSFREmbedQuery(task_description=task_description, query=text))
    query_vec = normalizeVec(query_vec)

    #add filters if applicable
    payload_filters = None if filters == [] or filters is None else Filter(must=filters)

    search_params = SearchParams(indexed_only=True)

    #search
    results = client.search(
        collection_name=collection,
        query_vector=query_vec,
        query_filter=payload_filters,
        with_payload=True,
        limit=max_results,
        score_threshold=min_score,
        search_params=search_params
    )

    #format results into JSON with payload
    output = []
    for point in results:
        fields = {
            'id': point.id,
            'sim_score': point.score
        }
        fields.update(point.payload)
        output.append(fields)
    return output

#WRAPPERS FOR USE CASE
#####################################################
def postsToPoints(posts:list[dict]) -> list[PointStruct]:
    points = []

    for post in posts:
        embedding = getEmbeddingOllama(prompt=f'{post['retitle_ml']}\n\n{post['summary_ml']}')
        embedding = normalizeVec(embedding)
        payload = {
            'story_id': post['story_id'],
            'topic_id': post['topic_id'],
            'category_ml': post['category_ml'],
            'used_in_newsletter': post['used_in_newsletter'],
            'newsletter_date': post['newsletter_date'],
            'created_at': post['created_at'],
            'post_publish_time': post['post_publish_time']
        }
        point = PointStruct(
            id=post['post_id'],
            vector=embedding,
            payload=payload
        )
        points.append(point)
    return points

def storiesToPoints(stories:list[dict]) -> list[PointStruct]:
    points = []

    for story in stories:
        embedding = getEmbeddingOllama(prompt=f'{story['headline_ml']}\n\n{story['summary_ml']}')
        embedding = normalizeVec(embedding)
        payload = {
            'story_id': story['story_id'],
            'topic_id': story['topic_id'],
            'used_in_newsletter': story['used_in_newsletter'],
            'newsletter_date': story['newsletter_date'],
            'created_at': story['created_at'],
            'posts_summarized': story['posts_summarized'],
            'posts': story['posts'],
            'daily_i_score_ml': story['daily_i_score_ml']
        }
        point = PointStruct(
            id=story['story_id'],
            vector=embedding,
            payload=payload
        )
        points.append(point)
    return points

def embedAndUpsertPosts(posts:list[dict]):
    points = postsToPoints(posts)
    upsertPoints(collection=QDRANT_POST_COLLECTION, points=points)

def embedAndUpsertStories(stories:list[dict]):
    points = storiesToPoints(stories)
    upsertPoints(collection=QDRANT_STORY_COLLECTION, points=points)

def searchStories(text:str, max_results:int, min_score:float=0.0, match_filters:dict={}, min_datetime=MIN_DATETIME_DEFAULT, max_datetime=MAX_DATETIME_DEFAULT) -> list[dict]:
    #construct filters
    filters = []
    filters.append(FieldCondition(key='created_at', range=DatetimeRange(gt=min_datetime, lt=max_datetime)))

    if match_filters != {}:
        for key in match_filters:
            filters.append(FieldCondition(key=key, match=MatchValue(value=match_filters[key])))

    return searchCollection(collection=QDRANT_STORY_COLLECTION, task_description=promptconfigs.RAG_SEARCH_TASKS['similar_news'], text=text, max_results=max_results, min_score=min_score, filters=filters)

def updateStoriesPayload(point_ids:list, payload_fields:dict):
    updatePointsPayload(collection=QDRANT_STORY_COLLECTION, point_ids=point_ids, payload_fields=payload_fields)
