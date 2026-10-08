"""Stop queued work and close live clients for deleted local batches."""
from threading import Lock
_lock = Lock()
_cancelled = set()
_clients = {}

def is_cancelled(task_id):
    with _lock:
        return task_id in _cancelled

def register_client(task_id, client):
    with _lock:
        if task_id in _cancelled:
            client.close()
            raise RuntimeError('任务已删除，停止调用')
        _clients.setdefault(task_id, set()).add(client)
    original = client.chat.completions.create
    def guarded_create(*args, **kwargs):
        if is_cancelled(task_id):
            raise RuntimeError('任务已删除，停止调用')
        return original(*args, **kwargs)
    client.chat.completions.create = guarded_create

def unregister_client(task_id, client):
    with _lock:
        clients = _clients.get(task_id)
        if clients is not None:
            clients.discard(client)
            if not clients: _clients.pop(task_id, None)
    client.close()

def cancel_batch_calls(task_id):
    with _lock:
        _cancelled.add(task_id)
        clients = list(_clients.get(task_id, ()))
    for client in clients:
        try: client.close()
        except Exception: pass
