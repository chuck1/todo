import datetime
import json
import os
import traceback
import pytz

import bson
import pymongo

import elephant
import jessica
import jessica.text
import weaver

import tasks.session
import tasks._datetime
import tasks.status

def breakpoint():
    import pdb;pdb.set_trace();

def errorResponse(err, responseBody):
    return {
        "statusCode": 400,
        "headers": {
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(traceback.format_exc()),
        "isBase64Encoded": False}

def process_filter_from_client(filt):
    def _f(k, v):
        if k.endswith('_id'):
            v = bson.objectid.ObjectId(v)
        return k, v

    return dict(_f(k, v) for k, v in filt.items())

class Handler:
    def __init__(self, e_tasks, e_texts):
        self.e_tasks = e_tasks
        self.e_texts = e_texts

    def task_list(self, body):
    
        if body['filter_string']:
            filt = json.loads(body['filter_string'])
        else:
            filt = {}
        filt = process_filter_from_client(filt)
        
        tasks_list = [tasks.task.Task(self.e_tasks, t).to_array() for t in self.e_tasks.find(filt)]
        texts_list = [jessica.text.Text(self.e_texts, t).to_array() for t in self.e_texts.find({'field': {'$exists': False}})]

        res = {
                'tasks': tasks_list,
                'texts': texts_list,
                'message': f'filt={filt}',
                }
        return res
     
    def texts_find(self, body):
        print('texts find', body)
        filt = process_filter_from_client(body['filter'])
        texts_list = [jessica.text.Text(self.e_texts, t).to_array() for t in self.e_texts.find(filt)]
        
        res = {
                'texts': texts_list,
                'message': f'filt={filt}',
                }
        return res
    
    def task_create(self, body):
        
        task0 = body['task']
        
        task0["due"] = tasks._datetime.stringToDatetime(task0["due"])
        
        res = self.e_tasks.put(None, task0)
    
        res = {'inserted_id': str(res.inserted_id)}
    
        return res
    
    def texts_create(self, body):
        text = body['text']

        if 'date' in text:
            text["date"] = tasks._datetime.stringToDatetime(text["date"])

        res = self.e_texts.put_new(text)
        res = {'inserted_id': str(res.inserted_id)}
        return res

    def texts_put(self, body):
        text_id = bson.objectid.ObjectId(body["text_id"]) if body["text_id"] is not None else None
        print(f'texts put: {body}')
        print(f'texts put: {text_id} {body["file"]}')

        res = self.e_texts.put(text_id, body['file']);
        
        if text_id is None:
            text_id = res.inserted_id

        return {
                'message': f'texts put: {text_id} {body["file"]}',
                'text_id': str(text_id),
                }

    def taskUpdateDue(self, body):
        due = tasks._datetime.stringToDatetime(body["due"])
        
        task_id = bson.objectid.ObjectId(body["task_id"])
    
        t0 = self.e_tasks.get_content(task_id)

        t0['due'] = due

        self.e_tasks.put(task_id, t0)

        return "update due success"
    
    def taskUpdateStatus(self, body):
        task_id = bson.objectid.ObjectId(body["task_id"])
        t0 = self.e_tasks.get_content(task_id)
        t0['status'] = body["status"]
        self.e_tasks.put(task_id, t0)
        t1 = self.e_tasks.get_content(task_id)
        return f"success {t1}"
   
    def taskDelete(self, body):
        task_id = body["task_id"]
        self.e_tasks.db.files.delete_one({'_id': task_id})
        return "success"
    
    def taskUpdateTitle(self, body):
        task_id = bson.objectid.ObjectId(body["task_id"])
        t0 = self.e_tasks.get_content(task_id)
        t0['title'] = body["title"]
        self.e_tasks.put(task_id, t0)
        return "success"
    
    def taskUpdateIsContainer(self, body):
        task_id = body["task_id"]
        self.session.updateIsContainer(self.session.filter_id(task_id), body["isContainer"])
        return "update isContainer success"
    
    def tasks_update_parent(self, body):
        task_id = bson.objectid.ObjectId(body["task_id"])
    
        t0 = self.e_tasks.get_content(task_id)

        t0['parent'] = bson.objectid.ObjectId(body["parent_id_str"])

        self.e_tasks.put(task_id, t0)

        return "success"
    
    def create_comment(self, body):
        self.session.taskPushPost(body["task_id"], body["text"])
    
        return "push post success"
    
    def processBody(self, event, body):
 
        functions = {
                "tasks list": self.task_list,
                "tasks create": self.task_create,
                "update_status": self.taskUpdateStatus,
                "update_title": self.taskUpdateTitle,
                "update_due": self.taskUpdateDue,
                "update_parent": self.tasks_update_parent,
                "update_is_container": self.taskUpdateIsContainer,
                "delete": self.taskDelete,
                "texts find": self.texts_find,
                "texts create": self.texts_create,
                "texts put": self.texts_put,
                }
   
        try:
            command = body["command"]
            f = functions[command]
            return f(body)
        except Exception as e:
            return traceback.format_exc()

def lambda_handler(event, context):
    
    session = None
    responseBody = None

    try:
        body = json.loads(event["body"])
        username = event["requestContext"]["authorizer"]["claims"]['cognito:username']

        db_name_tasks = body['database_tasks']
        db_name_texts = body['database_texts']
        db_name_weavr = 'weaver1'

        #session = tasks.session.Session(body['database'], username)
        
        client = pymongo.MongoClient(os.environ['MONGO_URI'])

        e_tasks = elephant.database_global.DatabaseGlobal(client[db_name_tasks], "master")
        e_texts = jessica.EngineDB(client[db_name_texts], "master")
        e_weavr = weaver.Engine(elephant.collection_local.CollectionLocal(client.otter1.weaver1))
        
        commands = body['commands']

        print('commands', commands)

        handler = Handler(e_tasks, e_texts, e_weavr)
        #handler.texts_engine = jessica.EngineDB('texts_personal')

        responseBody = json.dumps([handler.processBody(event, b) for b in commands])

        print('response', responseBody)
        
        return {
            "statusCode": 200,
            "headers": {
                'Access-Control-Allow-Origin': '*',
            },
            "body": responseBody,
            "isBase64Encoded": False}

    except Exception as e:
        traceback.print_exc()
        return errorResponse(e, repr(e) + " event: " + str(event))
    
def print_dict(d, level):
    for id_, t in d.items():
        print("-"*level + str(id_))
        print_dict(t.get("children", {}), level+1)

def _test_lambda(commands, database_tasks='test_tasks', database_texts='test_texts'):
    body = {
            'commands': commands,
            'database_tasks': database_tasks,
            'database_texts': database_texts,
            }

    res = lambda_handler({
        "body": json.dumps(body),
        "requestContext": {"authorizer": {"claims": {'cognito:username': 'charlesrymal-at-gmail.com'}}}}, {})

    return res

def test1():
    c = {
        "command": "tasks list",
        "filter_string": "",
        }
    res = _test_lambda([c], database_tasks='tasks1')

    print(res['body'])
    
    data = json.loads(res['body'])[0]
    
    print()
    print(data)
    print()

    task_list = data['tasks']

    for t in task_list:
        print(t)

def test3():
    res0 = _test_lambda([{
			"command": "tasks create",
                        "task": {
			"title": "test",
			"due": None,
			"parent": None,
                        }
        }])
    
    print(json.loads(res0['body'])[0])

    i0 = json.loads(res0['body'])[0]['inserted_id']

    res1 = _test_lambda([{
			"command": "tasks create",
                        "task": {
    			    "title": "test",
    			    "due": None,
			    "parent": None,
                            }
        }])

    i1 = json.loads(res1['body'])[0]['inserted_id']

    res2 = _test_lambda([{
        "command": "update_parent",
        "task_id": i0,
        "parent_id_str": i1,
        }])

    print(res2)

def test2(session):
    print('test2')

    res = session.task('test', None, None)

    print(res)

def test():
    test3()
    #test1()
    
    #session = tasks.session.Session('test', 'charlesrymal-at-gmail.com')
    #test2(session)






