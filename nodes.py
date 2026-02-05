import uuid
from datetime import datetime, timezone
from sqlitedict import SqliteDict
import os
import threading
import hashlib
import json
import hashlib
import copy

from contextvars import ContextVar

CURRENT_CONFIG_UID = ContextVar("CURRENT_CONFIG_UID", default=None)
CURRENT_PARSED_CONFIG = ContextVar("CURRENT_PARSED_CONFIG", default=None)

# Per-request runtime messages (server-side). Web clients can display them if
# the API endpoint includes them in the JSON response.
RUNTIME_MESSAGES = ContextVar("RUNTIME_MESSAGES", default=None)

# Guard to avoid running onAcceptServer multiple times for the same node
# during a single logical operation (e.g. setter -> update_data -> _save).
ACCEPT_GUARD = ContextVar("ACCEPT_GUARD", default=None)


class AcceptRejected(Exception):
    def __init__(self, payload=None):
        self.payload = payload or {}
        super().__init__(self.payload.get("error") or "Rejected")

def set_runtime_context(config_uid: str | None, parsed_config: dict | None):
    t1 = CURRENT_CONFIG_UID.set(config_uid)
    t2 = CURRENT_PARSED_CONFIG.set(parsed_config)
    # Reset per-request helpers
    RUNTIME_MESSAGES.set([])
    ACCEPT_GUARD.set(set())
    return (t1, t2)

def reset_runtime_context(tokens):
    t1, t2 = tokens
    CURRENT_CONFIG_UID.reset(t1)
    CURRENT_PARSED_CONFIG.reset(t2)
    # Clear per-request helpers
    RUNTIME_MESSAGES.set(None)
    ACCEPT_GUARD.set(None)


def push_message(text: str, level: str = "info"):
    """Add a runtime message to be returned by API endpoints."""
    try:
        msg = {"text": str(text), "level": str(level or "info")}
        lst = RUNTIME_MESSAGES.get()
        if lst is None:
            lst = []
            RUNTIME_MESSAGES.set(lst)
        lst.append(msg)
    except Exception:
        pass


def _accept_guard_key(node) -> str:
    return f"{getattr(node, '_config_uid', '')}:{getattr(node, '_schema_class_name', None) or node.__class__.__name__}:{getattr(node, '_id', '')}"

def _find_class_event_actions(parsed: dict, class_name: str, event_name: str, listener: str = "") -> list[dict]:
    cls_cfg = (parsed.get("classes") or {}).get(class_name) or {}
    actions: list[dict] = []
    for ev in (cls_cfg.get("events") or []):
        if (ev.get("event") or "") != event_name:
            continue
        ev_listener = str(ev.get("listener") or "").strip()

        # listener matching: как у api_node_event_web
        if listener:
            if ev_listener and ev_listener != listener:
                continue
        else:
            if ev_listener:
                continue

        actions.extend(ev.get("actions") or [])
    return actions

import inspect

def dispatch_node_class_event(node, event_name: str, input_data: dict) -> tuple[bool, dict]:
    parsed = CURRENT_PARSED_CONFIG.get()
    if not isinstance(parsed, dict):
        return True, {}

    
    cls_name = getattr(node, "_schema_class_name", None) or node.__class__.__name__

    listener = ""
    if isinstance(input_data, dict):
        listener = str(input_data.get("listener") or input_data.get("id") or "").strip()

    actions = _find_class_event_actions(parsed, cls_name, event_name, listener)
    if not actions:
        return True, {}

    prev_current = globals().get("CURRENT_NODE")
    globals()["CURRENT_NODE"] = node
    try:
        for a in actions:
            m = str(a.get("method") or "").strip()
            if not m:
                continue
            fn = getattr(node, m, None)
            
            c = fn.__code__
            print("FN:", fn, "qualname:", fn.__qualname__)
            print("file:", c.co_filename, "line:", c.co_firstlineno)
            print("freevars:", c.co_freevars, "vars:", c.co_varnames)
            print("bytecode_len:", len(c.co_code), "hash:", hash(c.co_code))

            if not callable(fn):
                return False, {"error": f"Handler method '{m}' not found for event {event_name}"}

            r = fn(input_data)

            
            if isinstance(r, tuple) and len(r) >= 1:
                ok = bool(r[0])
                data = r[1] if len(r) > 1 and isinstance(r[1], dict) else {}
                if not ok:
                    return False, (data or {})
            else:
                
                pass

        return True, {}
    finally:
        globals()["CURRENT_NODE"] = prev_current


def run_on_accept_server_once(node, saved_state: dict, input_data: dict | None = None) -> None:
    """Run config ClassEvent 'onAcceptServer' at most once per request per node.

    Raises AcceptRejected if rejected.
    """
    guard = ACCEPT_GUARD.get()
    if guard is None:
        guard = set()
        ACCEPT_GUARD.set(guard)

    key = _accept_guard_key(node)
    if key in guard:
        return
    guard.add(key)

    payload = dict(input_data or {})
    payload["_saved_state"] = dict(saved_state or {})
    ok, out = dispatch_node_class_event(node, "onAcceptServer", payload)
    if not ok:
        # Also attach runtime messages if any
        # If handler used nodes.message() (Node.Message), attach it as message payload too
        try:
            ui_msgs = getattr(node, "_ui_message", None)
            if isinstance(ui_msgs, list) and ui_msgs:
                out = dict(out or {})
                out.setdefault("messages", ui_msgs)
                out.setdefault("message", ui_msgs[-1])
                # one-shot: keep consistent with other UI hints
                try:
                    delattr(node, "_ui_message")
                except Exception:
                    pass
        except Exception:
            pass
        raise AcceptRejected(out)


STORAGE_BASE_PATH = 'node_storage'
os.makedirs(STORAGE_BASE_PATH, exist_ok=True)
SCHEMES_DB_PATH = os.path.join(STORAGE_BASE_PATH, "node_schemes.sqlite")
try:
    _SCHEMES_STORAGE = SqliteDict(SCHEMES_DB_PATH, autocommit=True)
except Exception:
    
    _SCHEMES_STORAGE = {}

_NODE_CLASS_REGISTRY = {}

class Node:
    
    _schemes = {}
    
    _class_storages = {}
    _storage_locks = {}  
    _instance_locks = {}  
    
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        
        
        if cls.__name__ != "Node":
            _NODE_CLASS_REGISTRY[cls.__name__] = cls
    @classmethod
    def _resolve_node_class(cls, class_or_name):
        
        if isinstance(class_or_name, type):
            return class_or_name
        if isinstance(class_or_name, str):
            name = class_or_name.strip()
            if not name:
                return None
            return _NODE_CLASS_REGISTRY.get(name)
        return class_or_name
    
    @classmethod
    def _resolve_class(cls, class_or_name):
        
        if isinstance(class_or_name, str):
            name = class_or_name.strip()
            if not name:
                raise ValueError("Empty class name")

            
            g = getattr(cls, "__dict__", {})
            mod_globals = getattr(__import__(cls.__module__), "__dict__", {})

            
            if name in mod_globals and isinstance(mod_globals[name], type):
                return mod_globals[name]

            raise ValueError(f"Unknown node class: {name}")

        
        if isinstance(class_or_name, type):
            return class_or_name

        raise TypeError(f"Invalid class spec: {class_or_name!r}")

    
    def __init__(self, node_id=None, config_uid=None):
        self._id = node_id or str(uuid.uuid4())
        self._config_uid = config_uid
        
        self._schema_class_name = getattr(self, "_schema_class_name", None) or self.__class__.__name__
        self._storage = None
        self._data_cache = None  
        
        
        if self._id not in Node._instance_locks:
            Node._instance_locks[self._id] = threading.RLock()
        
        self._lock = Node._instance_locks[self._id]
        
        with self._lock:
            self._init_storage()
            
            if self._id not in self._storage:
                
                initial_data = {
                    '_id': self._id,
                    '_class': self.__class__.__name__
                }
                self._storage[self._id] = {
                    '_id': self._id,
                    '_class': self.__class__.__name__,
                    '_config_uid': config_uid,
                    '_data': initial_data,
                    '_created_at': datetime.now(timezone.utc).isoformat(),
                    '_updated_at': datetime.now(timezone.utc).isoformat()
                }
            else:
                
                node_data = self._storage[self._id]
                if '_data' not in node_data:
                    node_data['_data'] = {}

                if node_data['_data'] == None:
                    node_data['_data'] = {}

                
                
                node_data['_data']['_id'] = self._id
                node_data['_data']['_class'] = self.__class__.__name__
                
                node_data['_updated_at'] = datetime.now(timezone.utc).isoformat()
                self._storage[self._id] = node_data
    
    @property
    def _data(self):
        
        with self._lock:
            if self._data_cache is None:
                if self._id in self._storage:
                    stored = self._storage[self._id]
                    
                    data = dict(stored.get('_data', {}) or {})

                    
                    data.setdefault('_class', self.__class__.__name__)

                    
                    data['_id'] = normalize_own_uid(
                        self._config_uid,
                        self.__class__.__name__,
                        data.get('_id') or self._id
                    )

                    self._data_cache = data
                else:
                    self._data_cache = {}
            return self._data_cache

    
    @_data.setter
    def _data(self, value):
        
        with self._lock:
            if self._id in self._storage:
                node_data = self._storage[self._id]
                old = node_data.get('_data')
                saved_state = dict(old) if isinstance(old, dict) else {}

                # make new value visible to handler via cache
                self._data_cache = dict(value) if isinstance(value, dict) else value

                # run accept hook BEFORE persisting
                run_on_accept_server_once(self, saved_state)

                # persist what handler left in cache (it may have modified _data)
                to_write = self._data_cache
                if isinstance(to_write, dict):
                    node_data['_data'] = dict(to_write)
                else:
                    node_data['_data'] = to_write
                node_data['_updated_at'] = datetime.now(timezone.utc).isoformat()
                self._storage[self._id] = node_data
    
    def _save(self):
        
        with self._lock:
            if self._id in self._storage:
                node_data = self._storage[self._id]

                # snapshot state currently stored in DB (before modifications)
                old = node_data.get("_data")
                saved_state = dict(old) if isinstance(old, dict) else {}

                stored = node_data.get("_data")
                if not isinstance(stored, dict):
                    stored = {}

                
                if isinstance(getattr(self, "_data", None), dict):
                    stored = dict(self._data)
                
                stored['_class'] = self.__class__.__name__
                stored['_id'] = normalize_own_uid(self._config_uid, self.__class__.__name__, stored.get('_id') or self._id)    

                
                # expose new state to handler
                self._data_cache = dict(stored)

                # run accept hook BEFORE persisting (only once per request)
                run_on_accept_server_once(self, saved_state)

                # persist what handler left in cache (it may have modified _data)
                to_write = self._data_cache
                if isinstance(to_write, dict):
                    node_data["_data"] = dict(to_write)
                else:
                    node_data["_data"] = stored

                node_data["_updated_at"] = datetime.now(timezone.utc).isoformat()
                self._storage[self._id] = node_data
                return True
            return False
        
    def _open(self, *, new_tab: bool = True):
        
        try:
            #import nodes as _nodes_mod
            #host = getattr(_nodes_mod, "CURRENT_NODE", None)
            #if host is None:
            import nodes as _nodes_mod
            host = getattr(_nodes_mod, "CURRENT_NODE", None) or self

            host._ui_open = {
                "config_uid": str(getattr(self, "_config_uid", "") or ""),
                # class name used by web-client routes (from config)
                "class_name": str(getattr(self, "_schema_class_name", None) or self.__class__.__name__),
                "node_id": str(getattr(self, "_id", "") or ""),
                "new_tab": bool(new_tab),
            }
        except Exception as e:
            pass

    def CloseNode(self):
        
        try:
            import nodes as _nodes_mod
            host = getattr(_nodes_mod, "CURRENT_NODE", None) or self
            host._ui_close = True
        except Exception:
            pass    

    
    @classmethod
    def create(self, node_id=None, initial_data=None):
        """
        Creates a new node of the same class and configuration.

        Args:
        node_id: ID of the new node (automatically generated if not specified)
        initial_data: Initial data for the new node

        Returns:
        Node: New node instance
        """
        new_node = self.__class__(node_id, self._config_uid)

        if initial_data:
            with new_node._lock:
                if new_node._id in new_node._storage:
                    node_data = new_node._storage[new_node._id]
                    if '_data' not in node_data or not isinstance(node_data.get('_data'), dict):
                        node_data['_data'] = {}

                    saved_state = dict(node_data.get('_data') or {})
                    new_state = dict(saved_state)

                    protected_keys = {'_id', '_class'}
                    for key, value in (initial_data or {}).items():
                        if key not in protected_keys:
                            new_state[key] = value

                    new_state['_id'] = normalize_own_uid(new_node._config_uid, new_node.__class__.__name__, new_node._id)
                    new_state['_class'] = new_node.__class__.__name__

                    new_node._data_cache = dict(new_state)

                    # run accept hook BEFORE persisting (only once per request)
                    run_on_accept_server_once(new_node, saved_state, dict(initial_data or {}))

                    # persist what handler left in cache (it may have modified _data)
                    to_write = new_node._data_cache
                    node_data['_data'] = dict(to_write) if isinstance(to_write, dict) else new_state
                    node_data['_updated_at'] = datetime.now(timezone.utc).isoformat()
                    new_node._storage[new_node._id] = node_data
                    new_node._data_cache = None

        return new_node

    def _init_storage(self):
        class_name = self.__class__.__name__
        storage_key = f"{class_name}_{self._config_uid}" if self._config_uid else class_name
        
        if storage_key not in Node._class_storages:
            # Lock for creating a new repository
            if storage_key not in Node._storage_locks:
                Node._storage_locks[storage_key] = threading.RLock()
            
            with Node._storage_locks[storage_key]:
                # Double check after getting blocked
                if storage_key not in Node._class_storages:
                    db_path = os.path.join(STORAGE_BASE_PATH, f"{storage_key}.sqlite")
                    Node._class_storages[storage_key] = SqliteDict(db_path, autocommit=True)
        
        self._storage = Node._class_storages[storage_key]
    
    def get_data(self):
        with self._lock:
            if self._id in self._storage:
                data = self._storage[self._id].get('_data', {})
                # Ensure that _id and _class are always present
                if '_id' not in data:
                    data['_id'] = self._id
                if '_class' not in data:
                    data['_class'] = self.__class__.__name__
                return data
            return {}
    
    def set_data(self, key, value):
        with self._lock:
            if self._id in self._storage:
                node_data = self._storage[self._id]
                if '_data' not in node_data or not isinstance(node_data.get('_data'), dict):
                    node_data['_data'] = {}
                saved_state = dict(node_data.get('_data') or {})

                base_state = self._data_cache if isinstance(self._data_cache, dict) else saved_state
                new_state = dict(base_state)
                new_state[key] = value
                new_state['_class'] = self.__class__.__name__
                new_state['_id'] = normalize_own_uid(self._config_uid, self.__class__.__name__, self._id)

                self._data_cache = dict(new_state)

                # run accept hook BEFORE persisting (only once per request)
                run_on_accept_server_once(self, saved_state, {key: value})

                # persist what handler left in cache (it may have modified _data)
                to_write = self._data_cache
                node_data['_data'] = dict(to_write) if isinstance(to_write, dict) else new_state
                node_data['_updated_at'] = datetime.now(timezone.utc).isoformat()
                self._storage[self._id] = node_data

    def update_data(self, data_dict):
        with self._lock:
            if self._id in self._storage:
                node_data = self._storage[self._id]
                if '_data' not in node_data or not isinstance(node_data.get('_data'), dict):
                    node_data['_data'] = {}
                saved_state = dict(node_data.get('_data') or {})

                base_state = self._data_cache if isinstance(self._data_cache, dict) else saved_state
                new_state = dict(base_state)
                protected_keys = {'_id', '_class'}
                for key, value in (data_dict or {}).items():
                    if key not in protected_keys:
                        new_state[key] = value

                new_state['_class'] = self.__class__.__name__
                new_state['_id'] = normalize_own_uid(self._config_uid, self.__class__.__name__, self._id)

                self._data_cache = dict(new_state)

                # run accept hook BEFORE persisting (only once per request)
                run_on_accept_server_once(self, saved_state, dict(data_dict or {}))

                # persist what handler left in cache (it may have modified _data)
                to_write = self._data_cache
                node_data['_data'] = dict(to_write) if isinstance(to_write, dict) else new_state
                node_data['_updated_at'] = datetime.now(timezone.utc).isoformat()
                self._storage[self._id] = node_data

    def delete(self):
        """Recursively delete a node and all its descendants"""
        with self._lock:
            # Сначала получаем всех детей (поддерживаем оба формата)
            children_nodes = self.GetChildren()
            
            # Рекурсивно удаляем всех потомков
            for child in children_nodes:
                child.delete()
            
            # Затем удаляем узел сам
            if self._id in self._storage:
                del self._storage[self._id]
                if self._id in Node._instance_locks:
                    del Node._instance_locks[self._id]
            
            # Удаляем связь с родителем, если она есть
            parent_info = self._data.get("_parent")
            if parent_info:
                try:
                    parent_class_name = parent_info.get("class", parent_info.get("_class"))
                    parent_id = parent_info.get("id", parent_info.get("_id"))
                    if parent_class_name and parent_id:
                        parent_cls = self._resolve_node_class(parent_class_name)
                        if parent_cls and issubclass(parent_cls, Node):
                            parent_node = parent_cls.get(parent_id, self._config_uid)
                            if parent_node:
                                parent_node.RemoveChild(self._id)
                except Exception as e:
                    print(f"Error removing from parent: {e}")
    
    @classmethod
    def get(cls, node_id, config_uid=None):
        storage_key = f"{cls.__name__}_{config_uid}" if config_uid else cls.__name__
        
        # Make sure the storage is initialized
        if storage_key not in cls._class_storages:
            # Lock for loading storage
            if storage_key not in cls._storage_locks:
                cls._storage_locks[storage_key] = threading.RLock()
            
            with cls._storage_locks[storage_key]:
                # Double check after getting blocked
                if storage_key not in cls._class_storages:
                    db_path = os.path.join(STORAGE_BASE_PATH, f"{storage_key}.sqlite")
                    
                    if not os.path.exists(db_path):
                        return None
                    
                    # Load an existing repository
                    try:
                        cls._class_storages[storage_key] = SqliteDict(db_path, autocommit=True)
                    except Exception:
                        return None
        
        storage = cls._class_storages[storage_key]
        
        if node_id in storage:
            return cls(node_id, config_uid)
        else:
            return None
    
    @classmethod
    def get_all(cls, config_uid=None):
        storage_key = f"{cls.__name__}_{config_uid}" if config_uid else cls.__name__
        
        if storage_key not in cls._class_storages:
            # Lock for loading storage
            if storage_key not in cls._storage_locks:
                cls._storage_locks[storage_key] = threading.RLock()
            
            with cls._storage_locks[storage_key]:
                # Double check after getting blocked
                if storage_key not in cls._class_storages:
                    db_path = os.path.join(STORAGE_BASE_PATH, f"{storage_key}.sqlite")
                    if not os.path.exists(db_path):
                        return {}
                    cls._class_storages[storage_key] = SqliteDict(db_path, autocommit=True)
        
        storage = cls._class_storages[storage_key]
        return {node_id: cls(node_id, config_uid) for node_id in storage.keys()}
    
    @classmethod
    def find(cls, condition_func, config_uid=None):
        results = {}
        for node_id, node in cls.get_all(config_uid).items():
            if condition_func(node):
                results[node_id] = node
        return results
    
    def to_dict(self):
        with self._lock:
            if self._id in self._storage:
                result = self._storage[self._id].copy()
                # We ensure that _data contains the current _id and _class
                if '_data' in result:
                    result['_data']['_class'] = self.__class__.__name__
                    result['_data']['_id'] = normalize_own_uid(self._config_uid, self.__class__.__name__, result['_data'].get('_id') or self._id)
                return result
            return {}
    
    # --- class schema managers (persistent via SqliteDict) ---
    @classmethod
    def _load_schemes_for_class(cls):
        
        
        if hasattr(cls, "_schemes") and cls._schemes is not None:
            return cls._schemes
        
        try:
            stored = _SCHEMES_STORAGE.get(cls.__name__, None)
        except Exception:
            stored = None
        cls._schemes = stored or {}
        return cls._schemes

    @classmethod
    def _save_schemes_for_class(cls):
        
        try:
            _SCHEMES_STORAGE[cls.__name__] = cls._schemes or {}
           
            try:
                _SCHEMES_STORAGE.commit()
            except Exception:
                pass
        except Exception:
            pass

    @classmethod
    def _add_scheme(cls, name, key_types, value_types):
        schemes = cls._load_schemes_for_class()
        schemes[name] = {"keys": key_types, "values": value_types}
        cls._schemes = schemes
        cls._save_schemes_for_class()

    @classmethod
    def _remove_scheme(cls, name):
        schemes = cls._load_schemes_for_class()
        if name in schemes:
            del schemes[name]
            cls._schemes = schemes
            cls._save_schemes_for_class()

    @classmethod
    def _get_schemes(cls):
        return cls._load_schemes_for_class()


    def _sum_transaction(self, scheme_name, period=None, keys=None, values=None, meta=None):
        
        #schemes = self.__class__._get_schemes()
        #if scheme_name not in schemes:
        #    raise ValueError(f"Схема '{scheme_name}' не найдена для {self.__class__.__name__}. "
        #                     f"Зарегистрируй через {self.__class__.__name__}._add_scheme(...)")

        if keys is None:
            keys = []
        if values is None:
            values = []

        
        if period is None:
            period = datetime.now().strftime("%Y-%m-%d")

        txs = self._data.setdefault("_transactions", {}).setdefault(scheme_name, [])
        last_tx = txs[-1] if txs else None
        parent_id = last_tx["uid"] if last_tx else None

        # We take past balances
        balances = last_tx["balances"].copy() if last_tx else {}

        # Generating an analytics key
        key_str = "::".join(str(k) for k in keys)
        if key_str not in balances:
            balances[key_str] = [0] * len(values)

        # Updating the balance
        balances[key_str] = [old + delta for old, delta in zip(balances[key_str], values)]

        # uid и hash
        uid = str(uuid.uuid4())
        prev_hash = last_tx["hash"] if last_tx else None
        tx_hash = hashlib.sha256(
            f"{uid}{parent_id}{balances}{period}".encode()
        ).hexdigest()

        tx = {
            "uid": uid,
            "parent": parent_id,
            "child": None,
            "period": period,
            "keys": keys,
            "values": values,
            "balances": balances,
            "hash": tx_hash,
            "prev_hash": prev_hash,
            "meta": meta or {}
        }

        # Close the child of the previous one
        if last_tx:
            last_tx["child"] = uid

        txs.append(tx)
        self._data["_transactions"][scheme_name] = txs
        self._save()
        return uid

    def _get_balance(self, scheme_name):
        """Returns current balances according to the scheme"""
        txs = self._data.get("_transactions", {}).get(scheme_name, [])
        if not txs:
            return {}
        return txs[-1]["balances"]
    def _get_sum_transactions(self, scheme_name):
        """Returns the full chain of transactions according to the scheme"""
        return self._data.get("_transactions", {}).get(scheme_name, [])
    
    def _state_transaction(self, scheme_name, period=None, keys=None, values=None, meta=None):
        """Adds a state transaction to the specified schema (does not sum, but sets values)"""
        if keys is None:
            keys = []
        if values is None:
            values = []

        
        if period is None:
            period = datetime.now().strftime("%Y-%m-%d")

        txs = self._data.setdefault("_state_transactions", {}).setdefault(scheme_name, [])
        last_tx = txs[-1] if txs else None
        parent_id = last_tx["uid"] if last_tx else None

        
        key_str = "::".join(str(k) for k in keys)
        
        
        current_state = {key_str: values.copy()}

        # uid и hash
        uid = str(uuid.uuid4())
        prev_hash = last_tx["hash"] if last_tx else None
        tx_hash = hashlib.sha256(
            f"{uid}{parent_id}{current_state}{period}".encode()
        ).hexdigest()

        tx = {
            "uid": uid,
            "parent": parent_id,
            "child": None,
            "period": period,
            "keys": keys,
            "values": values,
            "state": current_state,  
            "hash": tx_hash,
            "prev_hash": prev_hash,
            "meta": meta or {}
        }

        
        if last_tx:
            last_tx["child"] = uid

        txs.append(tx)
        self._data["_state_transactions"][scheme_name] = txs
        self._save()
        return uid

    def _get_state_balance(self, scheme_name):
        """Returns the current state of the schema (the values ​​of the last transaction)"""
        txs = self._data.get("_state_transactions", {}).get(scheme_name, [])
        if not txs:
            return {}
        return txs[-1]["state"]  

    def _get_state_transactions(self, scheme_name):
        """Returns the complete chain of transactions for the state of the schema"""
        return self._data.get("_state_transactions", {}).get(scheme_name, [])
        
    def __str__(self):
        return f"{self.__class__.__name__}(id={self._id})"
    
    def __repr__(self):
        return self.__str__()
    
    def AddChild(self, child_class, child_id=None, child_data=None):
        """
        Add a child node.
        child_class: Node class OR string (logical class name from config)
        """
        with self._lock:
            child_cls = self._resolve_node_class(child_class)
            if child_cls is None:
                raise ValueError(
                    f"Unknown child class: {child_class!r}. Known: {sorted(_NODE_CLASS_REGISTRY.keys())}"
                )
            
            child_node = child_cls(child_id, self._config_uid)
            
            schema_name = None
            if isinstance(child_class, str) and child_class.strip():
                schema_name = child_class.strip()
                child_node._schema_class_name = schema_name
            
            # Получаем текущий список детей в нужном формате
            children_data = self._data.setdefault("_children", {})
            
            # Если children_data - список (старый формат), конвертируем в новый формат
            if isinstance(children_data, list):
                # Конвертируем старый формат в новый
                new_children = {}
                for child in children_data:
                    if isinstance(child, dict):
                        child_class_name = child.get("class", child.get("_class", ""))
                        child_id_value = child.get("id", child.get("_id", ""))
                        if child_class_name and child_id_value:
                            key = f"{child_class_name}${child_id_value}"
                            # Значение - полный uid в новом формате
                            value = normalize_own_uid(self._config_uid, child_class_name, child_id_value)
                            new_children[key] = value
                children_data = new_children
                self._data["_children"] = children_data
            
            # Добавляем нового ребенка в новом формате
            key = f"{child_cls.__name__}${child_node._id}"
            value = normalize_own_uid(child_node._config_uid, child_cls.__name__, child_node._id)
            children_data[key] = value
            
            # Устанавливаем родителя в данных ребенка
            child_node._data["_parent"] = {
                "class": self.__class__.__name__,
                "id": self._id
            }
            
            if child_data:
                child_node.update_data(child_data)
            
            self._save()
            child_node._save()
            return child_node




    def RemoveChild(self, child_id):
        with self._lock:
            children_data = self._data.get("_children", [])
            
            # Новый формат (dict)
            if isinstance(children_data, dict):
                # Ищем ключи, которые заканчиваются на указанный child_id
                keys_to_remove = []
                for key in children_data.keys():
                    if key.endswith(f"${child_id}"):
                        keys_to_remove.append(key)
                
                # Удаляем найденные ключи
                for key in keys_to_remove:
                    del children_data[key]
                
                self._data["_children"] = children_data
            
            # Старый формат (list)
            elif isinstance(children_data, list):
                # Фильтруем список, оставляя только тех детей, у которых id не совпадает
                children_data = [
                    child for child in children_data 
                    if isinstance(child, dict) and 
                    child.get("id") != child_id and 
                    child.get("_id") != child_id
                ]
                self._data["_children"] = children_data
            
            self._save()

    def GetChildren(self, level=None):
        with self._lock:
            children_data = self._data.get("_children", []) or []
            children_nodes = []
            
            # Обработка нового формата (dict)
            if isinstance(children_data, dict):
                for key, value in children_data.items():
                    # key: "ClassName$nodeId"
                    # value: "config_uid$ClassName$nodeId"
                    
                    # Разбираем ключ или значение
                    parts = key.split("$")
                    if len(parts) >= 2:
                        child_class_name = parts[0]
                        child_id = parts[1]
                    else:
                        # Пробуем разобрать значение
                        value_parts = value.split("$")
                        if len(value_parts) >= 3:
                            child_class_name = value_parts[-2]
                            child_id = value_parts[-1]
                        else:
                            continue
                    
                    child_cls = self._resolve_node_class(child_class_name)
                    if child_cls is None:
                        continue
                    

                    child_node = child_cls.get(child_id, self._config_uid)
                    if child_node is not None:
                        children_nodes.append(child_node)
            
            # Обработка старого формата (list)
            elif isinstance(children_data, list):
                for child_info in children_data:
                    if not isinstance(child_info, dict):
                        continue
                        
                    child_id = child_info.get("id") or child_info.get("_id")
                    child_class_name = child_info.get("class") or child_info.get("_class")
                    
                    if not child_id or not child_class_name:
                        continue
                    
                    child_cls = self._resolve_node_class(child_class_name)
                    if child_cls is None:
                        continue
                    
                    child_node = child_cls.get(child_id, self._config_uid)
                    if child_node is not None:
                        children_nodes.append(child_node)
            
            return children_nodes
                

    
    def PlugIn(self, plugins):
        """Request client-side plugins (e.g. BarcodeScanner).

        Example:
            self.PlugIn([{"type":"BarcodeScanner","id":"barcode_scan"}])

        Notes:
          - Stored as one-shot UI hint in `_ui_plugins`
          - Web client can use it to route scanner events to onInputWeb with listener=id
        """
        try:
            if not isinstance(plugins, list):
                return False
            norm = []
            for it in plugins:
                if isinstance(it, dict):
                    t = str(it.get("type") or "").strip()
                    pid = str(it.get("id") or it.get("listener") or "").strip()
                    if t:
                        d = dict(it)
                        if pid:
                            d["id"] = pid
                        d["type"] = t
                        norm.append(d)
            self._ui_plugins = norm
            return True
        except Exception:
            return False

    def Show(self, layout):
            """
            Server-side Show() for web client:
            handlers can call self.Show(layout), and web client will render it via nodalayout.py
            """
            self._ui_layout = layout
            return True

    def Message(self, text: str, level: str = "info"):
        """Request a top message popup in the web client."""
        try:
            msgs = getattr(self, "_ui_message", None)
            if not isinstance(msgs, list):
                msgs = []
            msgs.append({"text": str(text), "level": str(level or "info")})
            self._ui_message = msgs
        except Exception:
            pass

    def Dialog(self, dialog_id: str, title: str = "", *, positive: str = "OK", negative: str = "Cancel", layout=None, html: str = ""):
        """Request a dialog in the web client.

        dialog_id is used to generate listeners:
          <dialog_id>_positive / <dialog_id>_negative
        """
        self._ui_dialog = {
            "id": str(dialog_id or "dialog"),
            "title": str(title or ""),
            "positive": str(positive or "OK"),
            "negative": str(negative or "Cancel"),
            "layout": layout,
            "html": html,
        }




# --- Compatibility helpers (LLM.txt style) ---
# Some generated handlers call message(...) / Dialog(...) as free functions.
CURRENT_NODE = None


def message(text: str, level: str = "info"):
    n = globals().get("CURRENT_NODE")
    if n is not None and hasattr(n, "Message"):
        try:
            # Store one-shot UI hint on node
            r = n.Message(text, level)
            # Also store in runtime messages so API/save responses can surface it
            try:
                push_message(text, level)
            except Exception:
                pass
            return r
        except Exception:
            return None
    return None


def Dialog(dialog_id: str, title: str = "", positive: str = "OK", negative: str = "Cancel", layout=None, html: str = ""):
    n = globals().get("CURRENT_NODE")
    if n is not None and hasattr(n, "Dialog"):
        try:
            return n.Dialog(dialog_id, title, positive=positive, negative=negative, layout=layout, html=html)
        except Exception:
            return None
    return None

def CloseNode():
    n = globals().get("CURRENT_NODE")
    if n is not None and hasattr(n, "CloseNode"):
        try:
            return n.CloseNode()
        except Exception:
            return None
    return None    

def to_uid(nodes_list):
    out = []
    for n in (nodes_list or []):
        if not hasattr(n, "_id"):
            continue
        
        cls = getattr(n, "_schema_class_name", None) or getattr(n, "_class_name", None) or n.__class__.__name__
        #out.append(f"{cls}${n._id}")
        out.append(normalize_own_uid(n._config_uid, cls, n._id))
    return out

def parse_uid(uid: str):
    s = str(uid or "")
    if "$" in s:
        parts = str(uid).split("$")
        if len(parts) >= 3:
            # cfg$Class$Id
            return parts[-2], parts[-1]
        if len(parts) == 2:
            # Class$Id
            return parts[0], parts[1]
        # Id only
        return None, parts[0]
        return cls.strip(), nid.strip()
    return "", s.strip()



# def extract_internal_id(raw_id: str) -> str:
#     """
#     Accepts: "100" | "Class$100" | "cfg$Class$100"
#     Returns internal storage id: "100"
#     """
#     if raw_id is None:
#         return None
#     s = str(raw_id)
#     parts = s.split("$")
#     if len(parts) >= 3:
#         return parts[-1]
#     if len(parts) == 2:
#         return parts[1]
#     return s


def normalize_own_uid(config_uid: str, class_name: str, raw_id: str) -> str:
    """
    Returns normalized uid: "cfg$Class$100"
    """
    internal = extract_internal_id(raw_id)
    if internal is None:
        return None
    return f"{config_uid}${class_name}${internal}"

def parse_uid_any(uid):
    """
    Returns tuple: (uid_config, class_name, internal_id)

    Accepts:
      - "cfg$Class$Id"
      - "Class$Id"
      - "Id"
      - dict forms: {"_id": "...", "_class": "..."} or {"id": "...", "class": "..."}
    """
    if uid is None:
        return None, None, None

    # dict support
    if isinstance(uid, dict):
        raw_id = uid.get("_id") or uid.get("id")
        raw_class = uid.get("_class") or uid.get("class")
        # If raw_id itself can be composite, parse it too, but class from dict wins if present.
        c_uid, c_cls, c_id = parse_uid_any(raw_id)
        return c_uid, (raw_class or c_cls), c_id

    s = str(uid)
    parts = s.split("$")
    if len(parts) >= 3:
        # cfg$Class$Id  (if there are more, we still take last two as class/id)
        return parts[0], parts[-2], parts[-1]
    if len(parts) == 2:
        # Class$Id
        return None, parts[0], parts[1]
    # Id only
    return None, None, parts[0]


def extract_internal_id(raw_id: str) -> str:
    """
    "100" | "Class$100" | "cfg$Class$100" -> "100"
    """
    if raw_id is None:
        return None
    return parse_uid_any(raw_id)[2]


def _resolve_node_class(config_info, class_name):
    """
    Tries to extract the Python Node class for `class_name` from config_info.

    Supports a few common shapes:
      - config_info["classes"][class_name] is the class itself
      - config_info["classes"][class_name] is dict with keys: "class", "node_class", "cls"
      - config_info["classes"][class_name] is object with attrs: class_/node_class/cls
    """
    if not config_info:
        return None

    classes = None
    if isinstance(config_info, dict):
        classes = config_info.get("classes") or config_info.get("Classes") or config_info.get("node_classes")
    else:
        classes = getattr(config_info, "classes", None) or getattr(config_info, "node_classes", None)

    if not classes:
        return None

    entry = classes.get(class_name) if isinstance(classes, dict) else None
    if entry is None:
        return None

    # entry may already be the class
    if isinstance(entry, type):
        return entry

    # entry may be dict
    if isinstance(entry, dict):
        return entry.get("node_class") or entry.get("class") or entry.get("cls")

    # entry may be object
    return getattr(entry, "node_class", None) or getattr(entry, "class", None) or getattr(entry, "cls", None)


def from_uid(uid, config_uid, config_info):
    """
    Resolve uid to a Node instance.

    - uid can be: "cfg$Class$Id", "Class$Id", "Id", or dict with _id/_class.
    - config_uid argument has priority. If config_uid is None, uid's own config part is used.
    - If class is missing, tries to find the node by scanning all classes in config_info.
    """
    uid_cfg, cls_name, internal_id = parse_uid_any(uid)
    if internal_id is None:
        return None

    effective_config_uid = config_uid or uid_cfg

    # 1) If we have class name -> resolve class and get node
    if cls_name:
        node_class = _resolve_node_class(config_info, cls_name)
        if node_class is None:
            raise KeyError(f"Unknown class '{cls_name}' in uid '{uid}'")
        return node_class.get(internal_id, effective_config_uid)

    # 2) No class -> scan all known classes and find first where node exists
    #    This keeps backward compatibility with "Id only"
    classes = None
    if isinstance(config_info, dict):
        classes = config_info.get("classes") or config_info.get("Classes") or config_info.get("node_classes") or {}
    else:
        classes = getattr(config_info, "classes", None) or getattr(config_info, "node_classes", None) or {}

    if isinstance(classes, dict):
        class_names = list(classes.keys())
    else:
        # if somehow it's not dict, we can't scan
        class_names = []

    for cn in class_names:
        node_class = _resolve_node_class(config_info, cn)
        if not node_class:
            continue
        try:
            node = node_class.get(internal_id, effective_config_uid)
            if node is not None:
                return node
        except Exception:
            # some get() implementations may raise if not found; ignore and continue
            continue

    # Not found
    return None

