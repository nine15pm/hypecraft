import db

#log pipeline event
def logPipelineEvent(topic_id, content_datetime, step_name, event, payload=None):
    pipelineEvent = []
    pipelineEvent.append(
        {
            'topic_id': topic_id,
            'content_date': content_datetime,
            'pipeline_step': step_name,
            'event': event,
            'event_type': 'pipeline_run',
            'payload': payload,
        }
    )
    db.createPipelineEvent(pipelineEvent)

#get pipeline events for given date range to figure out status
def getPipelineEvents(topic_id, min_datetime, max_datetime):
    filters = {
        'topic_id': topic_id,
        'event_type': 'pipeline_run'
    }
    return db.getPipelineEvents(min_datetime=min_datetime, max_datetime=max_datetime, filters=filters)