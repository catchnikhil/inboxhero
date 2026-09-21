# Roll Number: evernorth-aai-1177619

def remember(key, value, source):
    return {"status":"stored","key":key,"value":value,"source":source}

def recall(query):
    return {"facts":[f"Example fact matching {query}"]}

def compose_email(to, subject, body):
    return {"to":to,"subject":subject,"body":body,"status":"drafted"}

def move_email(id, folder):
    return {"id":id,"folder":folder,"status":"moved"}
