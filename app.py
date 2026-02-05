from flask import Flask, render_template, redirect, url_for, request, flash, jsonify, abort, after_this_request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user

from collections import OrderedDict
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
from sqlalchemy import select, text
import sqlalchemy as sa
import base64
import requests
from urllib.parse import urlparse
from flask import send_file
import io
from datetime import datetime, timezone
import json
from flask_sockets import Sockets
from geventwebsocket.handler import WebSocketHandler
from geventwebsocket import WebSocketError
from gevent.pywsgi import WSGIServer
from sqlitedict import SqliteDict
import qrcode
from io import BytesIO
from collections import defaultdict
from flask import g
import pytz
from ast import parse, FunctionDef, fix_missing_locations
import ast
import inspect

# ==================================================================
# Handlers loading (server): file-first, DB blob fallback
# Used to replace direct base64+exec blocks without changing endpoint logic.
# ==================================================================
def _handlers_file_path(config_uid: str) -> str:
    root_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(root_dir, "Handlers", str(config_uid), "handlers.py")


def _load_server_handlers_ns(config_uid, config):
    """Return an isolated namespace with server node handlers.

    Priority:
      1) Handlers/<config_uid>/handlers.py (same as client approach)
      2) config.nodes_server_handlers (base64 blob) as fallback
    Returns an empty dict if nothing is available.
    """
    isolated_globals = {}

    fp = _handlers_file_path(config_uid)
    try:
        if os.path.isfile(fp):
            with open(fp, "r", encoding="utf-8") as f:
                code = f.read()
            compiled = compile(code, fp, "exec")
            exec(compiled, isolated_globals)
            return isolated_globals
    except Exception:
        # Keep old behavior: endpoints will fall back to DB blob (or 404)
        pass

    try:
        if getattr(config, "nodes_server_handlers", None):
            code = base64.b64decode(config.nodes_server_handlers).decode("utf-8")
            compiled = compile(code, f"<db_handlers:{config_uid}>", "exec")
            exec(compiled, isolated_globals)
            return isolated_globals
    except Exception:
        # Keep old behavior: endpoints will handle errors as they did before
        pass

    return isolated_globals

import base64
from flask.json.provider import DefaultJSONProvider
import os
import time
import traceback
from flask import session
from functools import wraps
from urllib.parse import parse_qs
import logging
from flask_babel import Babel, _,format_datetime,format_date
import re
from nodes import extract_internal_id 
import nodes as _nodes_mod

from extensions import db, login_manager



logging.getLogger("geventwebsocket.handler").setLevel(logging.ERROR)
import ast
import inspect

#******************************************************************
#CHANGE IT WITH YOUR VALUES
DEEPSEEK_API_KEY = 'YOUR_KEY'
ADMIN_LOGIN = 'YOUR_LOGIN'
FLASK_SECRET= 'YOUR_KEY'
#******************************************************************


DEEPSEEK_API_URL = 'https://api.deepseek.com/v1/chat/completions'

LMSTUDIO_API_URL = os.environ.get("LMSTUDIO_API_URL", "http://127.0.0.1:1234/v1/chat/completions")
LMSTUDIO_MODEL = os.environ.get("LMSTUDIO_MODEL", "local-model")
LMSTUDIO_API_KEY = os.environ.get("LMSTUDIO_API_KEY", "") 

NL_FORMAT = "1.1"



NODE_CLASS_CODE = '''
from nodes import Node, message, Dialog, to_uid, from_uid, CloseNode
'''

NODE_CLASS_CODE_ANDROID = '''
from nodes import Node
'''

ANDROID_IMPORTS_TEMPLATE = '''from nodesclient import RefreshTab,SetTitle,CloseNode,RunGPS,StopGPS,UpdateView,Dialog,ScanBarcode,GetLocation,AddTimer,StopTimer,ShowProgressButton,HideProgressButton,ShowProgressGlobal,HideProgressGlobal,Controls,SetCover,getBase64FromImageFile,convertImageFilesToBase64Array,saveBase64ToFile,convertBase64ArrayToFilePaths,UpdateMediaGallery
from android import *
from nodes import NewNode, DeleteNode, GetAllNodes, GetNode, GetAllNodesStr, GetRemoteClass, CreateDataSet, GetDataSet, DeleteDataSet,to_uid, from_uid
from com.dv.noda import DataSet
from com.dv.noda import DataSets
from com.dv.noda import SimpleUtilites as su
from datasets import GetDataSetData

# Configuration constants
current_module_name="{uid}"
current_configuration_url="{config_url}"
_data_dir = su.get_data_dir(current_module_name)
_downloads_dir = su.get_downloads_dir(current_module_name)

'''

pending_responses = {}

pending_remote_requests = defaultdict(dict)


def api_auth_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth = request.authorization
        user = None
        if auth:
            user = check_api_auth(auth.username, auth.password)
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401

        if not bool(getattr(user, 'can_api', False)):
            return jsonify({'error': 'Forbidden'}), 403

        cfg_uid = kwargs.get('config_uid') or kwargs.get('uid')
        if cfg_uid and not user_can_access_config(user, str(cfg_uid)):
            return jsonify({'error': 'Forbidden'}), 403

        g.api_user = user
        return f(*args, **kwargs)
    return decorated_function

def check_api_auth(username, password):

    user = db.session.execute(
        select(User).where(User.email == username)
    ).scalar_one_or_none()
    
    if user and check_password_hash(user.password, password):
        return user
    return None


def user_can_access_config(user: 'User', config_uid: str) -> bool:
    """Config is accessible if user owns it or it is explicitly shared to them."""
    if not user or not config_uid:
        return False
    cfg = db.session.execute(
        select(Configuration).where(Configuration.uid == str(config_uid))
    ).scalar_one_or_none()
    if not cfg:
        return False
    if cfg.user_id == user.id:
        return True
    return bool(
        db.session.execute(
            select(UserConfigAccess).where(
                UserConfigAccess.user_id == user.id,
                UserConfigAccess.config_id == cfg.id,
            )
        ).scalar_one_or_none()
    )

def extract_method_body_from_code(module_code, class_name, method_name):
    
    try:
        tree = ast.parse(module_code)
        
        for node in ast.walk(tree):
            if (isinstance(node, ast.ClassDef) and 
                node.name == class_name):
                
                for class_node in node.body:
                    if (isinstance(class_node, ast.FunctionDef) and 
                        class_node.name == method_name):
                        
                        # Get start and end lines method
                        start_line = class_node.lineno - 1
                        end_line = class_node.end_lineno
                        
                        # Split code into lines
                        lines = module_code.split('\n')
                        
                        # Extract lines body method
                        body_lines = []
                        for i in range(start_line + 1, end_line):
                            if i >= len(lines):
                                break
                            line = lines[i]
                            # Remove indentation (first 8 spaces, corresponding indent method)
                            if line.startswith(' ' * 8):
                                line = line[8:]
                            elif line.startswith('    ' * 2):  # Alternative option: 2 levels indentation
                                line = line[8:]
                            body_lines.append(line)
                        
                        # Join and return body method without indentation
                        return '\n'.join(body_lines).rstrip()
        
        return None
    except Exception as e:
        print(f"Error extracting method body for {class_name}.{method_name}: {str(e)}")
        return None

def sync_methods_from_code(config, exclude_methods=None):
    
    if not config.nodes_handlers and not config.nodes_server_handlers:
        return
    
    try:
        #print(f"Syncing methods for config: {config.name}")
        
        # For Android/Python handlers
        if config.nodes_handlers:
            module_code = base64.b64decode(config.nodes_handlers).decode('utf-8')
            #print(f"Android handlers code length: {len(module_code)}")
            sync_android_methods_from_code(config, module_code, exclude_methods)
        
        # For Server /Python handlers
        if config.nodes_server_handlers:
            module_code = base64.b64decode(config.nodes_server_handlers).decode('utf-8')
            #print(f"Server handlers code length: {len(module_code)}")
            sync_server_methods_from_code(config, module_code, exclude_methods)
        
        db.session.commit()
        
    except Exception as e:
        print(f"Error syncing methods from code: {str(e)}")
        db.session.rollback()

def sync_android_methods_from_code(config, module_code, exclude_methods=None):
    
    # Find all methods inside classes (excluding methods class Node)
    code_methods = {}
    tree = ast.parse(module_code)
    
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            class_name = node.name
            # Skip base class Node
            if class_name == 'Node':
                continue
                
            code_methods[class_name] = []
            
            for class_node in node.body:
                if isinstance(class_node, ast.FunctionDef):
                    method_name = class_node.name
                    # Skip magic methods, private and example_method
                    if (not method_name.startswith('__') and 
                        method_name != 'example_method' and
                        method_name != '__init__'):
                        code_methods[class_name].append(method_name)
    
    # Sync with database
    for class_obj in config.classes:
        if class_obj.name in code_methods:
            # Existing methods in DB for Android/Python
            existing_methods = {m.code: m for m in class_obj.methods 
                              if m.engine == 'android_python'}
            
            # Methods from code-Add new
            for method_name in code_methods[class_obj.name]:
                if method_name not in existing_methods:
                    # Create new method in DB (only if not in exclusions)
                    if exclude_methods and (class_obj.name, method_name) in exclude_methods:
                        continue
                        
                    new_method = ClassMethod(
                        name=method_name,
                        source='internal',
                        engine='android_python',
                        code=method_name,
                        class_id=class_obj.id
                    )
                    db.session.add(new_method)
                    #print(f"Added Android method from code: {class_obj.name}.{method_name}")
            
            # Remove methods, that are not in code (except exclusions)
            for method_code, method_obj in existing_methods.items():
                if (method_code not in code_methods[class_obj.name] and 
                    not (exclude_methods and (class_obj.name, method_code) in exclude_methods)):
                    # Not remove methods, that were added via UI
                    if method_obj.name != method_code:
                        continue
                    db.session.delete(method_obj)
                    #print(f"Removed Android method not in code: {class_obj.name}.{method_code}")

def remove_method_from_code(config, class_name, method_name, engine):
    
    try:
        if engine == 'android_python' and config.nodes_handlers:
            module_code = base64.b64decode(config.nodes_handlers).decode('utf-8')
            
            
            is_valid, error = validate_python_syntax(module_code)
            if not is_valid:
                flash(f"Invalid module syntax before removal: {error}", 'danger')
                return False
            
            updated_code = remove_method_from_module(module_code, class_name, method_name)
            
            
            is_valid, error = validate_python_syntax(updated_code)
            if not is_valid:
                flash(f"Invalid module syntax after method removal: {error}", 'danger')
                return False
                
            config.nodes_handlers = base64.b64encode(updated_code.encode('utf-8')).decode('utf-8')
            db.session.add(config)
            db.session.commit() 
            print(f"Removed method from Android code: {class_name}.{method_name}")
            return True
        
        elif engine == 'server_python' and config.nodes_server_handlers:
            module_code = base64.b64decode(config.nodes_server_handlers).decode('utf-8')
            
            
            is_valid, error = validate_python_syntax(module_code)
            if not is_valid:
                flash(f"Invalid module syntax before removal: {error}", 'danger')
                return False
            
            updated_code = remove_method_from_module(module_code, class_name, method_name)
            
            
            is_valid, error = validate_python_syntax(updated_code)
            if not is_valid:
                flash(f"Invalid module syntax after method removal: {error}", 'danger')
                return False
                
            config.nodes_server_handlers = base64.b64encode(updated_code.encode('utf-8')).decode('utf-8')
            
            # Also update the server handlers file
            handlers_dir = os.path.join('Handlers', config.uid)
            os.makedirs(handlers_dir, exist_ok=True)
            handlers_file_path = os.path.join(handlers_dir, 'handlers.py')
            with open(handlers_file_path, 'w', encoding='utf-8') as f:
                f.write(updated_code)

            db.session.add(config)
            db.session.commit()    
            print(f"Removed method from Server code: {class_name}.{method_name}")
            return True
            
    except Exception as e:
        #print(f"Error removing method from code: {str(e)}")
        flash(f"Error removing method from code: {str(e)}", 'danger')
        return False

def remove_method_from_module(module_code, class_name, method_name):
    
    lines = module_code.split('\n')
    class_start = -1
    class_indent = 0
    in_target_class = False
    
    # Search start target class
    for i, line in enumerate(lines):
        if line.strip().startswith(f'class {class_name}('):
            class_start = i
            class_indent = len(line) - len(line.lstrip())
            in_target_class = True
            break
    
    if class_start == -1:
        return module_code  # Class not found
    
    # Search method inside target class
    method_start = -1
    method_end = -1
    in_method = False
    method_indent = 0
    method_found = False
    
    for i in range(class_start + 1, len(lines)):
        line = lines[i]
        current_indent = len(line) - len(line.lstrip())
        
        # If exited za bounds class
        if current_indent <= class_indent and line.strip():
            break
        
        # Found start method inside target class
        if (line.strip().startswith(f'def {method_name}(') and 
            current_indent > class_indent and
            in_target_class and not method_found):
            method_start = i
            method_indent = current_indent
            in_method = True
            method_found = True
            continue
        
        # If inside method
        if in_method:
            
            if current_indent <= method_indent and line.strip():
                method_end = i
                break
            
            # If this is end line
            if i == len(lines) - 1:
                method_end = i + 1
                break
    
    # Delete if method found
    if method_start != -1 and method_end != -1:
        new_lines = lines[:method_start] + lines[method_end:]
        return '\n'.join(new_lines)
    
    return module_code

def sync_server_methods_from_code(config, module_code, exclude_methods=None):
    
    
    code_methods = {}
    tree = ast.parse(module_code)
    
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            class_name = node.name
            code_methods[class_name] = []
            
            for class_node in node.body:
                if isinstance(class_node, ast.FunctionDef):
                    method_name = class_node.name
                    # Skip magic methods, private and example_method
                    if (not method_name.startswith('__') and 
                        method_name != 'example_method' and
                        method_name != '__init__'):
                        code_methods[class_name].append(method_name)
    
    # sync with DB
    for class_obj in config.classes:
        if class_obj.name in code_methods:
            # Existing methods in DB for Server /Python
            existing_methods = {m.code: m for m in class_obj.methods 
                              if m.engine == 'server_python'}
            
            # Methods from code-Add new
            for method_name in code_methods[class_obj.name]:
                if method_name not in existing_methods:
                    # Create new method in DB (only if not in exclusions)
                    if exclude_methods and (class_obj.name, method_name) in exclude_methods:
                        continue
                        
                    new_method = ClassMethod(
                        name=method_name,
                        source='internal',
                        engine='server_python',
                        code=method_name,
                        class_id=class_obj.id
                    )
                    db.session.add(new_method)
                    print(f"Added Server method from code: {class_obj.name}.{method_name}")
            
            # Remove methods, that are not in code (except exclusions)
            for method_code, method_obj in existing_methods.items():
                if (method_code not in code_methods[class_obj.name] and 
                    not (exclude_methods and (class_obj.name, method_code) in exclude_methods)):
                    # Not remove methods, that were added via UI
                    if method_obj.name != method_code:
                        continue
                    db.session.delete(method_obj)
                    print(f"Removed Server method not in code: {class_obj.name}.{method_code}")


def add_new_method_to_class(module_code, class_name, method_name, method_body):

    lines = module_code.split('\n')
    class_start = -1
    class_indent = 0
    
    #  Search start class
    for i, line in enumerate(lines):
        if line.strip().startswith(f'class {class_name}('):
            class_start = i
            class_indent = len(line) - len(line.lstrip())
            break
    
    if class_start == -1:
        return module_code  # Class not found
    
    # Search end class
    class_end = -1
    for i in range(class_start + 1, len(lines)):
        current_indent = len(lines[i]) - len(lines[i].lstrip())
        if current_indent <= class_indent and lines[i].strip():
            class_end = i
            break
    
    if class_end == -1:
        class_end = len(lines)
    

    method_indent = ' ' * (class_indent + 4)
    body_indent = ' ' * (class_indent + 8)
    
    method_code = f'{method_indent}def {method_name}(self, input_data=None):\n'
    
    # Add method with intendations
    for line in method_body.split('\n'):
        
        if line.strip():
            method_code += f'{body_indent}{line}\n'
        else:
            method_code += f'{body_indent}\n'  
    
    # check tuple return
    has_return_tuple = any('return True,' in line or 'return False,' in line for line in method_body.split('\n'))
    
    if not has_return_tuple:
        method_code += f'{body_indent}return True, {{}}\n'
    
    # past method
    new_lines = lines[:class_end] + [method_code] + lines[class_end:]
    return '\n'.join(new_lines)

def add_method_to_class(module_code, class_name, method_name, method_body):
    
    is_valid, error = validate_python_syntax(module_code)
    if not is_valid:
        flash(f"Invalid module syntax before changes: {error}", 'danger')
        return None
    

    if method_exists_in_code(module_code, class_name, method_name):
        updated_code = update_existing_method(module_code, class_name, method_name, method_body)
    else:
        updated_code = add_new_method_to_class(module_code, class_name, method_name, method_body)
    
    is_valid, error = validate_python_syntax(updated_code)
    if not is_valid:
        flash(f"Invalid module syntax after method addition: {error}", 'danger')
        return None
    
    return updated_code

def update_existing_method(module_code, class_name, method_name, new_body):
    
    lines = module_code.split('\n')
    class_start = -1
    class_indent = 0
    in_target_class = False
    

    for i, line in enumerate(lines):
        if line.strip().startswith(f'class {class_name}('):
            class_start = i
            class_indent = len(line) - len(line.lstrip())
            in_target_class = True
            break
    
    if class_start == -1:
        return module_code  
    

    method_start = -1
    method_indent = 0
    method_found = False
    
    for i in range(class_start + 1, len(lines)):
        line = lines[i]
        current_indent = len(line) - len(line.lstrip())
        

        if current_indent <= class_indent and line.strip():
            break
        

        if (line.strip().startswith(f'def {method_name}(') and 
            current_indent > class_indent and
            in_target_class):
            method_start = i
            method_indent = current_indent
            method_found = True
            break
    
    if not method_found or method_start == -1:
        return module_code  
    

    method_end = -1
    for i in range(method_start + 1, len(lines)):
        current_indent = len(lines[i]) - len(lines[i].lstrip())
        if current_indent <= method_indent and lines[i].strip():
            method_end = i
            break
    
    if method_end == -1:
        method_end = len(lines)
    

    body_indent = ' ' * (method_indent + 4)
    new_method_lines = [lines[method_start]]  
    

    for line in new_body.split('\n'):
        if line.strip():  
            new_method_lines.append(f'{body_indent}{line}')
        else:  
            new_method_lines.append('')
    

    new_lines = lines[:method_start] + new_method_lines + lines[method_end:]
    return '\n'.join(new_lines)

def validate_python_syntax(code):

    try:
        ast.parse(code)
        return True, None
    except SyntaxError as e:
        error_msg = f"Syntax error {e.lineno}: {e.msg}"
        return False, error_msg
    except Exception as e:
        return False, f"Validation fault: {str(e)}"



#Server functions
from sqlitedict import SqliteDict

STORAGE_BASE_PATH = 'node_storage'


os.makedirs(STORAGE_BASE_PATH, exist_ok=True)

def get_locale():
    # if a user is logged in, use the locale from the user settings
    user = getattr(g, 'user', None)
    if user is not None:
        return user.locale
    # otherwise try to guess the language from the user accept
    # header the browser transmits.  We support de/fr/en in this
    # example.  The best match wins.
    return request.accept_languages.best_match(['de', 'en', 'ru'])

def get_timezone():
    user = getattr(g, 'user', None)
    if user is not None:
        return user.timezone

app = Flask(__name__)
app.config['BABEL_DEFAULT_LOCALE'] = 'en'

# -----------------------------------------------------------------------------
# UI template snippets (used in multiple editors)
# -----------------------------------------------------------------------------

UI_COMPONENT_TEMPLATES = OrderedDict([
    ('Text', '{"type":"Text","value":"my text"}'),
    ('Text(tag)', '{"type":"Text","value":"my text","radius":10,"background":"#F54927"}'),
    ('Picture', '{"type":"Picture","value":""}'),
    ('Button', '{"type":"Button","id":"btn_update","caption":"Simple button"}'),
    ('Switch', '{"type":"Switch","caption":"Setting 1","id":"sw1","value":"@sw1"}'),
    ('CheckBox', '{"type":"CheckBox","caption":"My checkbox","id":"cb1","value":"@cb1"}'),
    ('Input', '{"type":"Input","caption":"My input","id":"my_input1","input_type":"","value":"@my_input1"}'),
    ('Table', '{"type":"Table","id":"my_table","value":[]}'),
    ('Tabs', '{"type":"Tabs","value":[{"type":"Tab","id":"tab1","caption":"My tab1","layout":[]}]}'),
    ('DatasetField', '{"type":"DatasetField","dataset":"","value":""}'),
])


def get_ui_component_templates():
    """Return (buttons, map) for UI component templates used by editors."""
    buttons = [{'key': k, 'label': k} for k in UI_COMPONENT_TEMPLATES.keys()]
    return buttons, dict(UI_COMPONENT_TEMPLATES)


sockets = Sockets(app)


@app.before_request
def _enforce_web_access_modes():
    """Restrict Designer (server UI) for users without can_designer.

    Client UI is handled in client_app blueprint.
    API uses basic auth decorators.
    """
    if not getattr(current_user, "is_authenticated", False):
        return

    # allow landing / mode switch / logout
    if request.endpoint in {"index", "logout", "choose_mode", "static"}:
        return

    # allow API routes (their own auth)
    if (request.path or "").startswith("/api/"):
        return

    # allow client blueprint routes (blueprint has its own guard)
    if (request.path or "").startswith("/client"):
        return

    # everything else is Designer/Server UI
    if not bool(getattr(current_user, "can_designer", False)):
        abort(403)


LANGUAGES = {
    'en': 'English', 
    'ru': 'Русский'
}

def get_locale():
    
    lang = request.args.get('lang')
    if lang in LANGUAGES:
        session['current_language'] = lang
        return lang
    
    
    if 'current_language' in session and session['current_language'] in LANGUAGES:
        return session['current_language']
    
    
    lang_cookie = request.cookies.get('language')
    if lang_cookie in LANGUAGES:
        return lang_cookie
    
    
    if hasattr(g, 'user') and g.user is not None:
        return g.user.locale
    
   
    return request.accept_languages.best_match(LANGUAGES.keys())

def get_timezone():
    if hasattr(g, 'user') and g.user is not None:
        return g.user.timezone
    return 'UTC'


babel = Babel(app, locale_selector=get_locale, timezone_selector=get_timezone)


@app.context_processor
def utility_processor():
    return {
        'get_locale': get_locale,
        'LANGUAGES': LANGUAGES,
        'format_datetime': format_datetime,
        'format_date': format_date
    }

@app.route('/set_language/<lang>')
def set_language(lang):
    if lang in LANGUAGES:
        
        session['current_language'] = lang
        session.permanent = True  
        
        
        response = redirect(request.referrer or url_for('index'))
       
        response.set_cookie('language', lang, max_age=365*24*60*60)  # 1 год
        return response
    
    return redirect(request.referrer or url_for('index'))



class CustomJSONProvider(DefaultJSONProvider):
    def dumps(self, obj, **kwargs):
        kwargs.setdefault('ensure_ascii', False)
        kwargs.setdefault('indent', 4)
        return json.dumps(obj, **kwargs)

    def default(self, o):
        if isinstance(o, uuid.UUID):
            return str(o)
        return super().default(o)
app.json = CustomJSONProvider(app)

active_connections = defaultdict(dict)

#Node client

# Node browser WebSocket connections (separate channel from Rooms)
# Each item: {"ws": ws, "config_uid": str, "classes": set[str] | None}
node_ws_connections = []

def _cleanup_node_ws():
    """Remove closed/broken node WS connections."""
    global node_ws_connections
    alive = []
    for c in node_ws_connections:
        ws = c.get("ws")
        try:
            if ws is not None and not ws.closed:
                alive.append(c)
        except Exception:
            pass
    node_ws_connections = alive

def broadcast_node_change(config_uid: str, class_name: str, node_id: str | None = None, event: str = "changed"):
    """Broadcast a lightweight invalidation event to all subscribed node browser clients."""
    _cleanup_node_ws()
    payload = {
        "type": f"node.{event}",   # node.created / node.updated / node.deleted
        "config_uid": config_uid,
        "class": class_name,
        "id": node_id,
        "ts": datetime.now(timezone.utc).isoformat(),
    }

    dead = []
    for c in node_ws_connections:
        ws = c.get("ws")
        if ws is None:
            dead.append(c)
            continue

        # subscription filter
        sub_cfg = c.get("config_uid")
        sub_classes = c.get("classes")  # None -> all
        if sub_cfg and sub_cfg != config_uid:
            continue
        if sub_classes is not None and class_name not in sub_classes:
            continue

        try:
            ws.send(json.dumps(payload))
        except Exception:
            dead.append(c)

    if dead:
        node_ws_connections[:] = [c for c in node_ws_connections if c not in dead]

def handle_nodes_websocket(ws):
    """
    WebSocket channel for node browser.
    Client sends:
      {"type":"subscribe","config_uid":"...","classes":["A","B"]}  (classes optional)
    Server sends:
      {"type":"node.updated|node.created|node.deleted", ...}
    """
    subscription = {"ws": ws, "config_uid": None, "classes": None}
    node_ws_connections.append(subscription)

    while not ws.closed:
        try:
            msg = ws.receive()
            if msg is None:
                break
            data = json.loads(msg) if isinstance(msg, str) else msg
            mtype = data.get("type")

            if mtype == "subscribe":
                subscription["config_uid"] = data.get("config_uid")
                classes = data.get("classes")
                if classes is None:
                    subscription["classes"] = None
                else:
                    subscription["classes"] = set(classes)

                ws.send(json.dumps({
                    "type": "subscribed",
                    "config_uid": subscription["config_uid"],
                    "classes": list(subscription["classes"]) if subscription["classes"] is not None else None
                }))

            elif mtype == "ping":
                ws.send(json.dumps({"type": "pong"}))
        except Exception:
            break

    _cleanup_node_ws()



app.config['SECRET_KEY'] = FLASK_SECRET
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite'

app.config['SQLALCHEMY_BINDS'] = {
    # stored near db.sqlite by default
    'client': 'sqlite:///client.sqlite',
}

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024
app.config['USER_TIMEZONE'] = 'Europe/Moscow'
app.config['JSON_AS_ASCII'] = False  


TASKS_DB_PATH = 'tasks.db'

db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'index'


# ---------------------------------------------------------------
# Lightweight SQLite schema migration
#
# The project doesn't use Alembic. When we add new SQLAlchemy columns,
# existing sqlite DB files won't have them and the app can crash even on
# simple SELECTs (because SQLAlchemy selects all mapped columns).
#
# To keep upgrades zero-touch, we add missing columns with ALTER TABLE
# at startup, before any queries happen.

def _ensure_sqlite_schema():
    """
    Lightweight SQLite schema migration without Alembic.

    IMPORTANT:
    - db.create_all() does NOT add missing columns on SQLite.
    - SQLAlchemy selects all mapped columns; if a column is missing -> crash on SELECT.
    - This function must run BEFORE any queries.
    """
    try:
        inspector = sa.inspect(db.engine)
    except Exception as e:
        print("Could not create inspector:", e)
        return

    # 1) Ensure base tables exist (creates missing tables only)
    try:
        db.create_all()
    except Exception as e:
        print("Could not create_all:", e)

    # Client bind tables (optional)
    try:
        db.create_all(bind="client")
    except Exception:
        pass

    def _table_exists(name: str) -> bool:
        try:
            return name in inspector.get_table_names()
        except Exception:
            return False

    def _get_cols(table: str) -> set[str]:
        try:
            return {c["name"] for c in inspector.get_columns(table)}
        except Exception:
            return set()

    def _add_col(table: str, col_sql: str, col_name: str):
        # refresh cols lazily
        cols = _get_cols(table)
        if col_name in cols:
            return
        try:
            with db.engine.begin() as conn:
                conn.execute(sa.text(f"ALTER TABLE {table} ADD COLUMN {col_sql}"))
            print(f"Migration: {table} add column {col_name}")
        except Exception as e:
            print(f"Could not add column {table}.{col_name}:", e)

    def _create_index(sql: str, label: str):
        try:
            with db.engine.begin() as conn:
                conn.execute(sa.text(sql))
            print(f"Migration: {label}")
        except Exception as e:
            # indexes may already exist; keep silent-ish
            print(f"Could not create index ({label}):", e)

    # ------------------------------------------------------------
    # user table migrations
    # ------------------------------------------------------------
    if _table_exists("user"):
        ucols = _get_cols("user")
        if "config_display_name" not in ucols:
            _add_col("user", 'config_display_name VARCHAR(100) DEFAULT ""', "config_display_name")

        # Backward compatible defaults: existing users keep access
        if "can_designer" not in ucols:
            _add_col("user", "can_designer BOOLEAN DEFAULT TRUE", "can_designer")
        if "can_client" not in ucols:
            _add_col("user", "can_client BOOLEAN DEFAULT TRUE", "can_client")
        if "can_api" not in ucols:
            _add_col("user", "can_api BOOLEAN DEFAULT TRUE", "can_api")
        if "parent_user_id" not in ucols:
            _add_col("user", "parent_user_id INTEGER", "parent_user_id")

    # ------------------------------------------------------------
    # config_section migrations
    # ------------------------------------------------------------
    if _table_exists("config_section"):
        scols = _get_cols("config_section")
        if "commands" not in scols:
            _add_col("config_section", "commands TEXT", "commands")

    # ------------------------------------------------------------
    # dataset migrations
    # ------------------------------------------------------------
    if _table_exists("dataset"):
        dcols = _get_cols("dataset")
        if "view_template" not in dcols:
            _add_col("dataset", "view_template TEXT", "view_template")
        if "autoload" not in dcols:
            _add_col("dataset", "autoload BOOLEAN DEFAULT FALSE", "autoload")

    # ------------------------------------------------------------
    # configuration migrations
    # ------------------------------------------------------------
    if _table_exists("configuration"):
        ccols = _get_cols("configuration")

        if "content_uid" not in ccols:
            _add_col("configuration", "content_uid VARCHAR(100)", "content_uid")
        if "vendor" not in ccols:
            _add_col("configuration", "vendor TEXT", "vendor")

        # common_layouts JSON
        if "common_layouts" not in ccols:
            _add_col("configuration", "common_layouts JSON", "common_layouts")

        if "user_id" not in ccols:
            _add_col("configuration", "user_id INTEGER", "user_id")
            # best-effort fill for old rows
            try:
                first_user = db.session.execute(select(User)).scalar()
                if first_user:
                    with db.engine.begin() as conn:
                        conn.execute(
                            sa.text("UPDATE configuration SET user_id = :uid WHERE user_id IS NULL"),
                            {"uid": first_user.id},
                        )
                _create_index(
                    "CREATE INDEX IF NOT EXISTS ix_configuration_user_id ON configuration (user_id)",
                    "configuration.user_id index",
                )
            except Exception as e:
                print("Could not backfill configuration.user_id:", e)

        if "server_name" not in ccols:
            _add_col("configuration", 'server_name VARCHAR(100) DEFAULT ""', "server_name")

        if "nodes_handlers" not in ccols:
            _add_col("configuration", "nodes_handlers TEXT", "nodes_handlers")
        if "nodes_handlers_meta" not in ccols:
            _add_col("configuration", "nodes_handlers_meta JSON", "nodes_handlers_meta")

        if "nodes_server_handlers" not in ccols:
            _add_col("configuration", "nodes_server_handlers TEXT", "nodes_server_handlers")
        if "nodes_server_handlers_meta" not in ccols:
            _add_col("configuration", "nodes_server_handlers_meta JSON", "nodes_server_handlers_meta")

        if "version" not in ccols:
            _add_col("configuration", 'version VARCHAR(20) DEFAULT "00.00.01"', "version")

        if "last_modified" not in ccols:
            _add_col("configuration", "last_modified DATETIME", "last_modified")
            # fill nulls
            try:
                with db.engine.begin() as conn:
                    conn.execute(sa.text(
                        "UPDATE configuration SET last_modified = CURRENT_TIMESTAMP "
                        "WHERE last_modified IS NULL"
                    ))
            except Exception as e:
                print("Could not backfill configuration.last_modified:", e)

        # best-effort normalize existing rows (content_uid/vendor)
        try:
            for cfg in Configuration.query.all():
                if not getattr(cfg, "content_uid", None):
                    cfg.content_uid = str(uuid.uuid4())
                if not getattr(cfg, "vendor", None):
                    # keep existing behavior
                    cfg.vendor = (cfg.user.config_display_name or cfg.user.email) if cfg.user else ""
            db.session.commit()
        except Exception as e:
            print("Could not normalize configuration rows:", e)
            db.session.rollback()

    # ------------------------------------------------------------
    # config_class migrations (this is where your crash came from)
    # ------------------------------------------------------------
    if _table_exists("config_class"):
        cols = _get_cols("config_class")

        # legacy / structural fields
        if "has_storage" not in cols:
            _add_col("config_class", "has_storage BOOLEAN DEFAULT FALSE", "has_storage")
        if "class_type" not in cols:
            _add_col("config_class", "class_type VARCHAR(50)", "class_type")
        if "hidden" not in cols:
            _add_col("config_class", "hidden BOOLEAN DEFAULT FALSE", "hidden")

        if "section" not in cols:
            _add_col("config_class", "section VARCHAR(100)", "section")
        if "section_code" not in cols:
            _add_col("config_class", "section_code VARCHAR(100)", "section_code")

        if "display_name" not in cols:
            _add_col("config_class", "display_name VARCHAR(100)", "display_name")
        if "cover_image" not in cols:
            _add_col("config_class", "cover_image TEXT", "cover_image")

        # JSON/events column
        if "events" not in cols:
            _add_col("config_class", "events TEXT", "events")

        # display/layout fields
        if "display_image_web" not in cols:
            _add_col("config_class", 'display_image_web TEXT DEFAULT ""', "display_image_web")
        if "display_image_table" not in cols:
            _add_col("config_class", 'display_image_table TEXT DEFAULT ""', "display_image_table")
        if "init_screen_layout" not in cols:
            _add_col("config_class", 'init_screen_layout TEXT DEFAULT ""', "init_screen_layout")

        # commands UI fields
        if "commands" not in cols:
            _add_col("config_class", 'commands TEXT DEFAULT ""', "commands")
        if "use_standard_commands" not in cols:
            _add_col("config_class", "use_standard_commands BOOLEAN DEFAULT TRUE", "use_standard_commands")
        if "svg_commands" not in cols:
            _add_col("config_class", 'svg_commands TEXT DEFAULT ""', "svg_commands")

        # Migration tab fields
        if "migration_register_command" not in cols:
            _add_col("config_class", "migration_register_command BOOLEAN DEFAULT 0", "migration_register_command")
        if "migration_register_on_save" not in cols:
            _add_col("config_class", "migration_register_on_save BOOLEAN DEFAULT 0", "migration_register_on_save")
        if "migration_default_room_uid" not in cols:
            _add_col("config_class", 'migration_default_room_uid VARCHAR(36) DEFAULT ""', "migration_default_room_uid")
        if "migration_default_room_alias" not in cols:
            _add_col("config_class", 'migration_default_room_alias VARCHAR(100) DEFAULT ""', "migration_default_room_alias")

    # ------------------------------------------------------------
    # class_method migrations
    # ------------------------------------------------------------
    if _table_exists("class_method"):
        mcols = _get_cols("class_method")
        if "source" not in mcols:
            _add_col("class_method", 'source VARCHAR(100) DEFAULT "internal"', "source")
        if "server" not in mcols:
            _add_col("class_method", 'server VARCHAR(255) DEFAULT "internal"', "server")

    # ------------------------------------------------------------
    # room_objects migrations
    # ------------------------------------------------------------
    if _table_exists("room_objects"):
        rocols = _get_cols("room_objects")
        if "acknowledged_by" not in rocols:
            _add_col("room_objects", 'acknowledged_by JSON DEFAULT "[]"', "acknowledged_by")

    # ------------------------------------------------------------
    # config_event / config_event_action migrations (tables might be missing on old DB)
    # ------------------------------------------------------------
    # ensure tables exist
    try:
        if not _table_exists("config_event") or not _table_exists("config_event_action"):
            db.create_all()
    except Exception as e:
        print("Could not ensure config_event tables:", e)

    if _table_exists("config_event"):
        ecol = _get_cols("config_event")
        if "config_id" not in ecol:
            _add_col("config_event", "config_id INTEGER", "config_id")
            _create_index(
                "CREATE INDEX IF NOT EXISTS ix_config_event_config_id ON config_event (config_id)",
                "config_event.config_id index",
            )

    if _table_exists("config_event_action"):
        eacols = _get_cols("config_event_action")
        if "event_id" not in eacols:
            _add_col("config_event_action", "event_id INTEGER", "event_id")
            _create_index(
                "CREATE INDEX IF NOT EXISTS ix_config_event_action_event_id ON config_event_action (event_id)",
                "config_event_action.event_id index",
            )

# Run schema check immediately on import (works for `flask run` too)
try:
    with app.app_context():
        _ensure_sqlite_schema()
except Exception as _e:
    print('SQLite schema ensure skipped:', _e)

try:
    from client_app.routes import client_bp
    app.register_blueprint(client_bp)
except Exception as _e:
    print('Client blueprint not loaded:', _e)


class Dataset(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    uid = db.Column(db.String(36), default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(100))
    hash_indexes = db.Column(db.String(255))  
    text_indexes = db.Column(db.String(255))  
    view_template = db.Column(db.Text) 
    autoload = db.Column(db.Boolean, default=False)  
    config_id = db.Column(db.Integer, db.ForeignKey('configuration.id'))
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

    
    items = db.relationship('DatasetItem', backref='dataset', cascade='all, delete-orphan')

class DatasetItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    dataset_id = db.Column(db.Integer, db.ForeignKey('dataset.id'))
    item_id = db.Column(db.String(100))  
    data = db.Column(db.JSON)  
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

   
    __table_args__ = (
        db.Index('idx_dataset_item_id', 'dataset_id', 'item_id'),
    )


class Room(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    uid = db.Column(db.String(36), default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(100))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))


class RoomAlias(db.Model):
    """Room aliases bound to a configuration.

    Used by the web-client migration/registration commands.
    Stores mapping: alias -> Room.uid
    """

    __tablename__ = 'room_alias'

    id = db.Column(db.Integer, primary_key=True)
    alias = db.Column(db.String(100), nullable=False)
    room_uid = db.Column(db.String(36), nullable=False, default="")

    config_id = db.Column(db.Integer, db.ForeignKey('configuration.id', ondelete='CASCADE'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    __table_args__ = (
        db.UniqueConstraint('config_id', 'alias', name='uq_room_alias_config_alias'),
        db.Index('idx_room_alias_config', 'config_id'),
    )

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    config_display_name = db.Column(db.String(100), default="")

    # Access flags
    can_designer = db.Column(db.Boolean, default=False)  # Configurator/Designer
    can_client = db.Column(db.Boolean, default=False)    # Web Client
    can_api = db.Column(db.Boolean, default=False)       # HTTP API (basic auth)

    # User who created/owns this account ("admin" scope)
    parent_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    parent_user = db.relationship('User', remote_side=[id], backref=db.backref('children', lazy=True))

    configurations = db.relationship('Configuration', backref='user', lazy=True)


class UserConfigAccess(db.Model):
    __tablename__ = 'user_config_access'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    config_id = db.Column(db.Integer, db.ForeignKey('configuration.id', ondelete='CASCADE'), nullable=False, index=True)

    user = db.relationship('User', backref=db.backref('config_access', cascade='all, delete-orphan', lazy=True))
    config = db.relationship('Configuration', backref=db.backref('user_access', cascade='all, delete-orphan', lazy=True))

class UserDevice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    android_id = db.Column(db.String(100), nullable=False)
    device_model = db.Column(db.String(200))
    token = db.Column(db.String(200))
    last_connected = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    user = db.relationship('User', backref=db.backref('devices', lazy=True))  

class ConfigEvent(db.Model):
    __tablename__ = 'config_event'
    id = db.Column(db.Integer, primary_key=True)
    event = db.Column(db.String(100), nullable=False)  # onLaunch, onBarcode, etc.
    listener = db.Column(db.String(200), default="", nullable=False)
    config_id = db.Column(db.Integer, db.ForeignKey('configuration.id', ondelete='CASCADE'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
    actions = db.relationship('ConfigEventAction', backref='event_obj', cascade='all, delete-orphan', order_by='ConfigEventAction.id')

    def actions_as_dicts(self):
        """Converts event actions into dictionaries for JSON serialization"""
        result = []
        for action in self.actions:
            action_dict = {
                "action": action.action,
                "method": action.method,
                "source": action.source,
                "server": action.server,
                "postExecuteMethod": action.post_execute_method
            }
            
            action_dict = {k: v for k, v in action_dict.items() if v is not None and v != ""}
            result.append(action_dict)
        return result

class ConfigEventAction(db.Model):
    __tablename__ = 'config_event_action'
    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(50), default='run', nullable=False)   # run, runprogress, runasync
    source = db.Column(db.String(50), default='internal', nullable=False)
    server = db.Column(db.String(255), default="")
    method = db.Column(db.String(200), default="")
    post_execute_method = db.Column(db.String(200), default="")
    order = db.Column(db.Integer, default=0)  

    event_id = db.Column(db.Integer, db.ForeignKey('config_event.id', ondelete='CASCADE'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "action": self.action,
            "source": self.source,
            "server": self.server,
            "method": self.method,
            "postExecuteMethod": self.post_execute_method,
            "order": self.order,
        }
    
class Configuration(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    uid = db.Column(db.String(36), default=lambda: str(uuid.uuid4()))
    content_uid = db.Column(db.String(36), default=lambda: str(uuid.uuid4()))
    vendor = db.Column(db.String(100))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    version = db.Column(db.String(20), default="00.00.01")
    server_name = db.Column(db.String(100), default="") 
    last_modified = db.Column(db.DateTime, nullable=False, 
                            default=datetime.now,
                            onupdate=datetime.now)
    nodes_handlers = db.Column(db.Text)  
    nodes_handlers_meta = db.Column(db.JSON)  
    nodes_server_handlers = db.Column(db.Text, nullable=True)  
    nodes_server_handlers_meta = db.Column(db.JSON)
    classes = db.relationship('ConfigClass', backref='config', cascade='all, delete-orphan')
    datasets = db.relationship('Dataset', backref='config', cascade='all, delete-orphan')
    sections = db.relationship('ConfigSection', backref='config', cascade='all, delete-orphan')
    servers = db.relationship('Server', backref='config', cascade='all, delete-orphan')
    room_aliases = db.relationship('RoomAlias', backref='config', cascade='all, delete-orphan')
    config_events = db.relationship('ConfigEvent', backref='config', cascade='all, delete-orphan')
    common_layouts = db.Column(db.JSON, default=list)
    
    def update_last_modified(self):
        self.last_modified = datetime.now()
        db.session.commit()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        if not hasattr(self, 'version'):
            self.version = "00.00.01"
        if not hasattr(self, 'last_modified'):
            self.last_modified = datetime.now(timezone.utc)
class ConfigSection(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    code = db.Column(db.String(100))
    commands = db.Column(db.Text)
    config_id = db.Column(db.Integer, db.ForeignKey('configuration.id'))

class ConfigClass(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    config_id = db.Column(db.Integer, db.ForeignKey('configuration.id'))
    has_storage = db.Column(db.Boolean, default=False)  
    class_type = db.Column(db.String(50))  
    display_name = db.Column(db.String(100))  
    cover_image = db.Column(db.Text)  
    section = db.Column(db.String(100))  
    section_code = db.Column(db.String(100)) 
    methods = db.relationship('ClassMethod', backref='class_obj', cascade='all, delete-orphan')
    events = db.Column(db.JSON, default={})
    hidden = db.Column(db.Boolean, default=False)
    event_objs = db.relationship('ClassEvent', backref='class_obj', cascade='all, delete-orphan')
    # Display-related images / layouts
    display_image_web = db.Column(db.Text, default="")
    display_image_table = db.Column(db.Text, default="")
    init_screen_layout = db.Column(db.Text, default="")

    # Commands UI (string formats described in UI hints)
    commands = db.Column(db.Text, default="")
    use_standard_commands = db.Column(db.Boolean, default=True)
    svg_commands = db.Column(db.Text, default="")

    # Migration / registration helpers (used by web-client)
    migration_register_command = db.Column(db.Boolean, default=False)
    migration_register_on_save = db.Column(db.Boolean, default=False)
    # Stores Room.uid (string)
    migration_default_room_uid = db.Column(db.String(36), default="")
    # Stores RoomAlias.alias (string)
    migration_default_room_alias = db.Column(db.String(100), default="")
    

class ClassMethod(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    source = db.Column(db.String(100), default='internal')
    server = db.Column(db.String(255)) 
    engine = db.Column(db.String(50))
    
    code = db.Column(db.Text)
    class_id = db.Column(db.Integer, db.ForeignKey('config_class.id'))



class ClassEvent(db.Model):
    __tablename__ = 'class_event'
    id = db.Column(db.Integer, primary_key=True)
    event = db.Column(db.String(100), nullable=False)           
    listener = db.Column(db.String(200), default="", nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey('config_class.id', ondelete='CASCADE'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

    
    actions = db.relationship('EventAction', backref='event_obj', cascade='all, delete-orphan', order_by='EventAction.id')

    def actions_as_dicts(self):
        """Converts event actions into dictionaries for JSON serialization"""
        result = []
        for action in self.actions:
            action_dict = {
                "action": action.action,
                "method": action.method,
                "source": action.source,
                "server": action.server,
                "postExecuteMethod": action.post_execute_method
            }
            
            action_dict = {k: v for k, v in action_dict.items() if v is not None and v != ""}
            result.append(action_dict)
        return result

class EventAction(db.Model):
    __tablename__ = 'event_action'
    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(50), default='run', nullable=False)   # run, runprogress, runasync
    source = db.Column(db.String(50), default='internal', nullable=False)
    server = db.Column(db.String(255), default="")
    method = db.Column(db.String(200), default="")
    post_execute_method = db.Column(db.String(200), default="")
    order = db.Column(db.Integer, default=0)  

    event_id = db.Column(db.Integer, db.ForeignKey('class_event.id', ondelete='CASCADE'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "action": self.action,
            "source": self.source,
            "server": self.server,
            "method": self.method,
            "postExecuteMethod": self.post_execute_method,
            "order": self.order,
        }


class RoomObjects(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    room_uid = db.Column(db.String(36))
    config_uid = db.Column(db.String(36))
    class_name = db.Column(db.String(100))
    objects_data = db.Column(db.JSON) 
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    expires_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc) )

    acknowledged_by = db.Column(db.JSON, default=list) 
    
    __table_args__ = (
        db.Index('idx_room_objects', 'room_uid', 'config_uid', 'class_name'),
    )  

class Server(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    alias = db.Column(db.String(100), nullable=False)
    url = db.Column(db.String(255), nullable=False)
    config_id = db.Column(db.Integer, db.ForeignKey('configuration.id'))
    is_default = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

      

# Authorization
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))
@app.route('/update-device-token/<int:device_id>', methods=['POST'])
@login_required
def update_device_token(device_id):
    device = UserDevice.query.get_or_404(device_id)
    if device.user_id != current_user.id:
        abort(403)
    device.token = request.form.get('token')
    db.session.commit()
    flash('Token updated', 'success')
    return redirect(url_for('edit_profile'))

@app.route('/api/get-token', methods=['GET'])
@login_required
def get_token_by_android_id():
    android_id = request.args.get('android_id')
    if not android_id:
        return jsonify({'error': 'android_id is required'}), 400

    device = UserDevice.query.filter_by(user_id=current_user.id, android_id=android_id).first()
    if not device:
        return jsonify({'error': 'device not found'}), 404

    return jsonify({'token': device.token or ''})


@app.route('/edit-profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        current_user.email = request.form.get('email')
        if request.form.get('password'):
            current_user.password = generate_password_hash(request.form.get('password'))
        current_user.config_display_name = request.form.get('config_display_name')
        db.session.commit()
        flash(_('Profile updated successfully'), 'success')
        return redirect(url_for('dashboard'))
    
    devices = UserDevice.query.filter_by(user_id=current_user.id).all()
    return render_template('edit_profile.html', devices=devices)




@app.route('/admin')
@login_required
def admin_dashboard():
    if current_user.email != ADMIN_LOGIN:  
        abort(403)
    

    total_users = db.session.query(User).count()
    total_devices = db.session.query(UserDevice).count()
    
    
    active_users = set()
    for room_connections in active_connections.values():
        active_users.update(room_connections.keys())
    active_users_count = len(active_users)
    
    
    active_devices_count = sum(len(connections) for connections in active_connections.values())
    
    
    users_with_stats = db.session.query(
        User,
        db.func.count(UserDevice.id).label('device_count')
    ).outerjoin(UserDevice).group_by(User.id).all()
    
    return render_template('admin_dashboard.html',
                         total_users=total_users,
                         total_devices=total_devices,
                         active_users_count=active_users_count,
                         active_devices_count=active_devices_count,
                         users_with_stats=users_with_stats,active_connections=active_connections)


@app.route('/admin/user/<int:user_id>')
@login_required
def admin_user_detail(user_id):
    
    if current_user.email != ADMIN_LOGIN:
        abort(403)
    
    user = db.session.get(User, user_id)
    if not user:
        abort(404)
    
    
    devices = UserDevice.query.filter_by(user_id=user_id).all()
    
   
    configurations = Configuration.query.filter_by(user_id=user_id).all()
    
    
    rooms = Room.query.filter_by(user_id=user_id).all()
    
    
    is_active = any(user.email in connections for connections in active_connections.values())
    
    return render_template('admin_user_detail.html',
                         user=user,
                         devices=devices,
                         configurations=configurations,
                         rooms=rooms,
                         is_active=is_active)


@app.route('/admin/user/<int:user_id>/toggle-active', methods=['POST'])
@login_required
def admin_toggle_user_active(user_id):
    if current_user.email != ADMIN_LOGIN:
        abort(403)
    
    user = db.session.get(User, user_id)
    if not user:
        abort(404)
    
    flash(f'User status {user.email} changed', 'success')
    return redirect(url_for('admin_user_detail', user_id=user_id))


@app.template_filter('b64decode')
def b64decode_filter(s):
    if s:
        try:
            return base64.b64decode(s).decode('utf-8')
        except Exception as e:
            print(f"Decoding error: {str(e)}")
            return _("# Decoding error:")+ str(e)
    return ""

@app.route('/choose-mode')
@login_required
def choose_mode():
    return render_template('choose_mode.html')


@app.route('/users', methods=['GET'])
@login_required
def users_manage():
    # only Designer accounts can manage users
    if not bool(getattr(current_user, 'can_designer', False)):
        abort(403)

    # users created under current_user
    users = db.session.execute(
        select(User).where(User.parent_user_id == current_user.id).order_by(User.email)
    ).scalars().all()

    # configs owned by current_user (only these can be shared)
    cfgs = db.session.execute(
        select(Configuration).where(Configuration.user_id == current_user.id).order_by(Configuration.name)
    ).scalars().all()

    # map: user_id -> set(config_id)
    access_map = {}
    for u in users:
        ids = set()
        for a in (u.config_access or []):
            try:
                ids.add(int(a.config_id))
            except Exception:
                pass
        access_map[u.id] = ids

    return render_template('users_manage.html', users=users, configs=cfgs, access_map=access_map)


@app.route('/users/create', methods=['POST'])
@login_required
def users_create():
    if not bool(getattr(current_user, 'can_designer', False)):
        abort(403)

    email = (request.form.get('email') or '').strip()
    password = (request.form.get('password') or '').strip()
    if not email or not password:
        flash('Email и пароль обязательны', 'error')
        return redirect(url_for('users_manage'))

    exists = db.session.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if exists:
        flash('Такой email уже существует', 'error')
        return redirect(url_for('users_manage'))

    u = User(
        email=email,
        password=generate_password_hash(password),
        parent_user_id=current_user.id,
        can_designer=bool(request.form.get('can_designer')),
        can_client=bool(request.form.get('can_client')),
        can_api=bool(request.form.get('can_api')),
    )
    db.session.add(u)
    db.session.commit()

    # config access (only configs owned by current_user)
    cfg_ids = request.form.getlist('config_ids')
    owned_cfgs = db.session.execute(select(Configuration.id).where(Configuration.user_id == current_user.id)).scalars().all()
    owned_set = set(int(x) for x in owned_cfgs)
    for cid in cfg_ids:
        try:
            icid = int(cid)
        except Exception:
            continue
        if icid not in owned_set:
            continue
        db.session.add(UserConfigAccess(user_id=u.id, config_id=icid))
    db.session.commit()

    flash('Пользователь создан', 'success')
    return redirect(url_for('users_manage'))


@app.route('/users/<int:user_id>/update', methods=['POST'])
@login_required
def users_update(user_id: int):
    if not bool(getattr(current_user, 'can_designer', False)):
        abort(403)

    u = db.session.get(User, user_id)
    if not u or u.parent_user_id != current_user.id:
        abort(404)

    u.can_designer = bool(request.form.get('can_designer'))
    u.can_client = bool(request.form.get('can_client'))
    u.can_api = bool(request.form.get('can_api'))

    new_pwd = (request.form.get('password') or '').strip()
    if new_pwd:
        u.password = generate_password_hash(new_pwd)

    # rewrite config access set
    cfg_ids = request.form.getlist('config_ids')
    owned_cfgs = db.session.execute(select(Configuration.id).where(Configuration.user_id == current_user.id)).scalars().all()
    owned_set = set(int(x) for x in owned_cfgs)
    wanted = set()
    for cid in cfg_ids:
        try:
            icid = int(cid)
        except Exception:
            continue
        if icid in owned_set:
            wanted.add(icid)

    # delete old
    db.session.execute(
        sa.delete(UserConfigAccess).where(UserConfigAccess.user_id == u.id)
    )
    db.session.commit()

    for icid in sorted(wanted):
        db.session.add(UserConfigAccess(user_id=u.id, config_id=icid))
    db.session.commit()

    flash('Права обновлены', 'success')
    return redirect(url_for('users_manage'))


@app.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
def users_delete(user_id: int):
    if not bool(getattr(current_user, 'can_designer', False)):
        abort(403)
    u = db.session.get(User, user_id)
    if not u or u.parent_user_id != current_user.id:
        abort(404)
    db.session.delete(u)
    db.session.commit()
    flash('Пользователь удален', 'success')
    return redirect(url_for('users_manage'))

@app.route('/', methods=['GET', 'POST'])
def index():
    if current_user.is_authenticated:
        return redirect(url_for('choose_mode'))
    
    if request.method == 'POST':
        form_type = request.form.get('form_type')
        
        if form_type == 'login':
            email = request.form.get('email')
            password = request.form.get('password')
            user = db.session.execute(
                select(User).where(User.email == email)
            ).scalar_one_or_none()
            
            if user and check_password_hash(user.password, password):
                login_user(user)
                return redirect(url_for('choose_mode'))
            flash(_('Invalid email or password'), 'error')

        elif form_type == 'register':
            email = request.form.get('email')
            password = request.form.get('password')
            
            if db.session.execute(
                select(User).where(User.email == email)
            ).scalar_one_or_none():
                flash(_('Email already taken'), 'error')
            else:
                new_user = User(
                    email=email,
                    password=generate_password_hash(password),
                    can_designer=True,
                    can_client=True,
                    can_api=True,
                )
                db.session.add(new_user)
                db.session.commit()
                login_user(new_user)
                return redirect(url_for('choose_mode'))
    
    return render_template('index.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

#Rooms

@app.route('/create-room', methods=['POST'])
@login_required
def create_room():
    name = request.form.get('name', 'New room')
    new_room = Room(
        name=name,
        user_id=current_user.id
    )
    db.session.add(new_room)
    db.session.commit()
    return redirect(url_for('room_detail', room_uid=new_room.uid))

def generate_qr_code(data):
    import qrcode
    from io import BytesIO
    import base64
    
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill='black', back_color='white')
    
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")

@app.route('/room/<room_uid>')
@login_required
def room_detail(room_uid):
    room = Room.query.filter_by(uid=room_uid, user_id=current_user.id).first_or_404()
    
    with SqliteDict(TASKS_DB_PATH) as tasks_db:
        tasks = tasks_db.get(room_uid, [])
        active_tasks = [t for t in tasks if not t.get('_done')]
    
    
    ws_scheme = get_ws_scheme()
    ws_url = f"{ws_scheme}://{request.host}/ws?room={room.uid}"

    qr_img = generate_qr_code(ws_url)

    
    
    return render_template('room_detail.html', 
                         room=room,
                         tasks=tasks,
                         active_tasks=active_tasks,
                         ws_url=ws_url,
                         qr_img=qr_img)




@app.route('/delete-room/<room_uid>')
@login_required
def delete_room(room_uid):
    room = Room.query.filter_by(uid=room_uid, user_id=current_user.id).first_or_404()
    db.session.delete(room)
    db.session.commit()
    
    
    with SqliteDict(TASKS_DB_PATH) as tasks_db:
        if room.uid in tasks_db:
            del tasks_db[room.uid]
        tasks_db.commit()
    
    return redirect(url_for('dashboard') + '#rooms')

def get_connected_users(room_uid):
    """Returns a list of all connected users in the room."""
    if room_uid not in active_connections:
        return []
    
    users = []
    for username, ws in active_connections[room_uid].items():
        users.append({
            'user': username,
            'email': username,  
            'connection_time': datetime.now(timezone.utc).isoformat(),
            'status': 'connected'
        })
    return users

# Websocket handlers
def handle_websocket(ws, room_uid):
    
    print(f"New connection for room {room_uid}")
    user = None
    
    try:

        auth_header = ws.environ.get('HTTP_AUTHORIZATION')
        active_connections[room_uid][user] = ws
        user_connected_message = {
            'type': 'user_connected',
            'user': user,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        for conn_user, conn_ws in list(active_connections[room_uid].items()):
            try:
                if not conn_ws.closed:
                    conn_ws.send(json.dumps(user_connected_message))
            except WebSocketError:
                active_connections[room_uid].pop(conn_user, None)

        auth_success=False
        if auth_header and auth_header.startswith('Basic '):
             try:
                 credentials = base64.b64decode(auth_header[6:]).decode('utf-8')
                 username, password = credentials.split(':', 1)
                
                
                 with app.app_context():
                     user_obj = db.session.execute(
                         select(User).where(User.email == username)
                     ).scalar_one_or_none()
                    
                     if not user_obj or not check_password_hash(user_obj.password, password):
                         ws.close(code=4001)
                         return
                       
                     
                     user = user_obj.email
                     auth_success=True

                     #android_id = ws.environ.get('HTTP_ANDROID_ID')
                     #device_model = ws.environ.get('HTTP_DEVICE_MODEL')

                     query = parse_qs(ws.environ.get('QUERY_STRING', ''))
                     android_id = query.get('android_id', [None])[0]
                     device_model = query.get('device_model', [None])[0]

                     if android_id:
                        with app.app_context():
                            device = UserDevice.query.filter_by(user_id=user_obj.id, android_id=android_id).first()
                            if not device:
                                device = UserDevice(
                                    user_id=user_obj.id,
                                    android_id=android_id,
                                    device_model=device_model or "Unknown"
                                )
                                db.session.add(device)
                            else:
                                device.device_model = device_model or device.device_model
                                device.last_connected = datetime.now(timezone.utc)
                            db.session.commit()   

                     print(f"Authenticated user: {user}")
                   
             except Exception as e:
                 print(f"Auth error: {str(e)}")
                 ws.close(code=4001)
                 return
        else:
             
             #ws.close(code=4001)
             #return    
             pass

        
        init_message = ws.receive()
        if not init_message:
            return
            
        try:
            data = json.loads(init_message)
            if data.get('type') != 'connection':
                raise ValueError("First message must be connection type")
                
            user = data.get('user')
            if not user:
                raise ValueError("User not specified")
                
            
            active_connections[room_uid][user] = ws
            print(f"User {user} connected to room {room_uid}")
            
            
            is_debug_room = False
            room_name = ""
            with app.app_context():
                room = Room.query.filter_by(uid=room_uid).first()
                if room:
                    is_debug_room = ('debug' in room.name.lower() or room.name == 'Debug room')
                    room_name = room.name
            
            
            room_info = {
                'type': 'room_info',
                'is_debug_room': is_debug_room,
                'room_name': room_name,
                'room_uid': room_uid,
                'message': f'Connection to the room  "{room_name}" has been established'
            }
            ws.send(json.dumps(room_info))
            
            
            if is_debug_room:
                debug_message = {
                    'type': 'debug_connected',
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'user': user,
                    'message': f'The user {user}  has connected to the debug room.'
                }
                
                
                for conn_user, conn_ws in list(active_connections[room_uid].items()):
                    try:
                        if not conn_ws.closed:
                            conn_ws.send(json.dumps(debug_message))
                    except WebSocketError:
                        active_connections[room_uid].pop(conn_user, None)
            
            
            if not is_debug_room and auth_success:
                send_tasks_update(room_uid)
                send_nodes_update(room_uid, user)
            
            
            while True:
                message = ws.receive()
                if message is None:
                    break
                    
                try:
                    data = json.loads(message)
                    handle_ws_command(room_uid, user, data, auth_success)
                except json.JSONDecodeError:
                    print(f"Invalid JSON from {user}")
                    ws.send(json.dumps({'error': 'Invalid JSON format'}))
                
                #time.sleep(0.1)    

        except (ValueError, json.JSONDecodeError) as e:
            print(f"Connection error: {str(e)}")
            ws.send(json.dumps({'error': str(e)}))
            
    except WebSocketError as e:
        print(f"WebSocket error: {str(e)}")
    finally:
        
        if user and room_uid in active_connections:
            active_connections[room_uid].pop(user, None)
            
            user_disconnected_message = {
                'type': 'user_disconnected',
                'user': user,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
            for conn_user, conn_ws in list(active_connections[room_uid].items()):
                try:
                    if not conn_ws.closed:
                        conn_ws.send(json.dumps(user_disconnected_message))
                except WebSocketError:
                    active_connections[room_uid].pop(conn_user, None)

        if not ws.closed:
            ws.close()
        print(f"Connection closed for {user} in room {room_uid}")

def send_nodes_update(room_uid, user_id=None):
    """Sends objects to room clients, excluding those already confirmed"""
    with app.app_context():
        query = RoomObjects.query.filter_by(room_uid=room_uid)
        
        objects = query.order_by(RoomObjects.created_at.desc()).all()
        
        if room_uid in active_connections:
            for user, ws in list(active_connections[room_uid].items()):
                
                if user_id and user != user_id:
                    continue
                    
                objects_data = []
                for obj in objects:
                    
                    if user in (obj.acknowledged_by or []):
                        continue
                        
                    objects_data.append({
                        'object_id': obj.id,  
                        'config_uid': obj.config_uid,
                        'class_name': obj.class_name,
                        'objects': obj.objects_data,
                        'created_at': obj.created_at.isoformat()
                    })
                
                if objects_data:  
                    try:
                        if not ws.closed:
                            ws.send(json.dumps({
                                'type': 'nodes_update',
                                'objects': objects_data
                            }))
                    except WebSocketError:
                        active_connections[room_uid].pop(user, None)
                        print(f"Removed dead connection for {user}")       

def send_tasks_update(room_uid):
    """Sends a task update to all clients in the room"""
    with app.app_context():  
        with SqliteDict(TASKS_DB_PATH) as tasks_db:
            tasks = tasks_db.get(room_uid, [])
            active_tasks = [t for t in tasks if not t.get('_done') and not t.get('_blocked')]
            
            if room_uid in active_connections:
                for user, ws in list(active_connections[room_uid].items()):
                    try:
                        if not ws.closed: 
                            ws.send(json.dumps({
                                'type': 'tasks_update',
                                'data': active_tasks
                            }))
                    except WebSocketError:
                        
                        active_connections[room_uid].pop(user, None)
                        print(f"Removed dead connection for {user}")


# API for working with tasks
@app.route('/api/room/<room_uid>/tasks', methods=['POST'])
@api_auth_required
def add_tasks(room_uid):
    if not request.is_json:
        abort(400, description="Request must be JSON")
    
    tasks = request.json
    if not isinstance(tasks, list):
        abort(400, description="Tasks should be an array")
    
    with SqliteDict(TASKS_DB_PATH) as tasks_db:
        room_tasks = tasks_db.get(room_uid, [])
        
       
        for task in tasks:
            if not isinstance(task, dict):
                continue
                
            if 'uid' not in task:
                task['uid'] = str(uuid.uuid4())
            task['_created'] = datetime.now(timezone.utc).isoformat()
            room_tasks.append(task)
        
        tasks_db[room_uid] = room_tasks
        tasks_db.commit()
        
        # Sending an update via websocket
        active_tasks = [t for t in room_tasks if not t.get('_done') and not t.get('_blocked')]
        send_tasks_update(room_uid)
    
    return jsonify({"status": "success", "count": len(tasks)})

@app.route('/api/room/<room_uid>/tasks/available', methods=['GET'])
@api_auth_required
def get_available_task(room_uid):
    with SqliteDict(TASKS_DB_PATH) as tasks_db:
        room_tasks = tasks_db.get(room_uid, [])
        
        # Find the first available task
        for i, task in enumerate(room_tasks):
            if not task.get('_done') and not task.get('_blocked'):
                # Mark as blocked
                room_tasks[i]['_blocked'] = True
                room_tasks[i]['_blocked_at'] = datetime.now(timezone.utc).isoformat()
                tasks_db[room_uid] = room_tasks
                tasks_db.commit()
                
                # Sending an update via websocket
                active_tasks = [t for t in room_tasks if not t.get('_done') and not t.get('_blocked')]
                send_tasks_update(room_uid)
                
                return jsonify(task)
    
    return jsonify({"status": "no_tasks_available"}), 404

@app.route('/api/room/<room_uid>/tasks/<task_uid>/complete', methods=['POST'])
@api_auth_required
def complete_task(room_uid, task_uid):
    with SqliteDict(TASKS_DB_PATH) as tasks_db:
        room_tasks = tasks_db.get(room_uid, [])
        
        for i, task in enumerate(room_tasks):
            if task.get('uid') == task_uid:
                room_tasks[i]['_done'] = True
                room_tasks[i]['_completed_at'] = datetime.now(timezone.utc).isoformat()
                tasks_db[room_uid] = room_tasks
                tasks_db.commit()
                
                # Sending an update via websocket
                active_tasks = [t for t in room_tasks if not t.get('_done') and not t.get('_blocked')]
                send_tasks_update(room_uid)
                
                return jsonify({"status": "success"})
    
    return jsonify({"status": "task_not_found"}), 404

@app.route('/api/room/<room_uid>/tasks/completed', methods=['DELETE'])
@api_auth_required
def clear_completed_tasks(room_uid):
    with SqliteDict(TASKS_DB_PATH) as tasks_db:
        room_tasks = tasks_db.get(room_uid, [])
        
        # We leave only unfinished tasks
        updated_tasks = [t for t in room_tasks if not t.get('_done')]
        tasks_db[room_uid] = updated_tasks
        tasks_db.commit()
        
        # Sending an update via websocket
        active_tasks = [t for t in updated_tasks if not t.get('_done') and not t.get('_blocked')]
        send_tasks_update(room_uid)
    
    return jsonify({"status": "success", "remaining": len(updated_tasks)})


#Personal account
@app.route('/dashboard')
@login_required
def dashboard():
    stmt = select(Configuration).where(Configuration.user_id == current_user.id)
    configs = db.session.execute(stmt).scalars().all()
    
    stmt = select(Room).where(Room.user_id == current_user.id)
    rooms = db.session.execute(stmt).scalars().all()
    
    return render_template('dashboard.html', configs=configs, rooms=rooms)

@app.route('/delete-config/<uid>')
@login_required
def delete_config(uid):
    # Replace the execute with scalar() or first()
    config = db.session.scalar(
        select(Configuration)
        .where(Configuration.uid == uid, Configuration.user_id == current_user.id)
    )
    
    if config:
        db.session.delete(config)
        db.session.commit()
        flash(_('Configuration deleted'), 'success')

    return redirect(url_for('dashboard'))


@app.route('/upload-handlers/<uid>', methods=['POST'])
@login_required
def upload_handlers(uid):
    config = db.session.scalars(
        select(Configuration)
        .where(Configuration.uid == uid, Configuration.user_id == current_user.id)
    ).first()
    
    if not config:
        abort(404)
    
    upload_type = request.form.get('upload_type')
    handlers_data = {}

    file_content = None
    metadata = {
        'type': upload_type,
        'uploaded_at': datetime.now(timezone.utc).isoformat()
    }
    
    try:
        if upload_type == 'file':
            if 'python_file' not in request.files:
                flash(_('File not selected'), 'error')
                active_tab = request.form.get("active_tab", "danger")
                return redirect(url_for('edit_config', uid=uid,tab=active_tab))
            
            file = request.files['python_file']
            if file.filename == '':
                flash(_('File not selected'), 'error')
                active_tab = request.form.get("active_tab", "config")
                return redirect(url_for('edit_config', uid=uid,tab=active_tab))
            
            if not file.filename.endswith('.py'):
                flash(_('Only .py files allowed'), 'danger')
                active_tab = request.form.get("active_tab", "config")
                return redirect(url_for('edit_config', uid=uid,tab=active_tab))
            
            file_content = file.read().decode('utf-8')
            metadata['filename'] = file.filename
            
        elif upload_type == 'github':
            github_url = request.form.get('github_url')
            if not github_url:
                flash(_('Enter GitHub URL'), 'danger')
                return redirect(url_for('edit_config', uid=uid,tab=active_tab))
            
            
            parsed = urlparse(github_url)
            if 'raw.githubusercontent.com' not in parsed.netloc:
                flash(_('Use GitHub RAW URL'), 'danger')
                active_tab = request.form.get("active_tab", "config")
                return redirect(url_for('edit_config', uid=uid,tab=active_tab))
            
            response = requests.get(github_url)
            if response.status_code != 200:
                flash(_('Failed to load file'), 'error')
                active_tab = request.form.get("active_tab", "config")
                return redirect(url_for('edit_config', uid=uid,tab=active_tab))
            
            file_content = response.text
            metadata['url'] = github_url
            
        else:
            flash(_('Invalid upload type'), 'error')
            active_tab = request.form.get("active_tab", "config")
            return redirect(url_for('edit_config', uid=uid,tab=active_tab))
        
        android_imports = ANDROID_IMPORTS_TEMPLATE.format(
            uid=config.uid, 
            config_url=url_for('get_config', uid=config.uid, _external=True)
        )
        
        
        if 'from nodes import Node' not in file_content:
            
            file_content =android_imports + NODE_CLASS_CODE_ANDROID + '\n' + file_content
        
        config.nodes_handlers = base64.b64encode(file_content.encode('utf-8')).decode('utf-8')
        config.nodes_handlers_meta = metadata
        db.session.commit()
        
        
        sync_classes_from_android_handlers(config)
        sync_methods_from_code(config)
        
        flash(_('Handlers loaded successfully'), 'success')
    
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')
    active_tab = request.form.get("active_tab", "config") 
    return redirect(url_for('edit_config', uid=uid, tab=active_tab))

def sync_classes_from_android_handlers(config):
    
    if not config.nodes_handlers:
        return
    
    try:
        module_code = base64.b64decode(config.nodes_handlers).decode('utf-8')
        tree = ast.parse(module_code)
        
        
        node_classes = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                
                for base in node.bases:
                    if (isinstance(base, ast.Name) and base.id == 'Node') or \
                       (isinstance(base, ast.Attribute) and base.attr == 'Node'):
                        
                        if node.name != 'Node':
                            node_classes.append(node.name)
                        break
        
        
        existing_classes = {c.name: c for c in config.classes}
        
        for class_name in node_classes:
            if class_name not in existing_classes:
                
                new_class = ConfigClass(
                    name=class_name,
                    display_name=class_name,
                    config_id=config.id,
                    class_type='custom_process',
                    section_code='android'
                )
                db.session.add(new_class)
                print(f"Added new Android class from code: {class_name}")
        
        
        for class_name, class_obj in existing_classes.items():
            if (class_name not in node_classes and 
                class_obj.section_code == 'android' and
                class_obj.name != 'Node'):  
                db.session.delete(class_obj)
                print(f"Removed Android class not in code: {class_name}")
        
        db.session.commit()
        
    except Exception as e:
        print(f"Error syncing classes from Android handlers: {str(e)}")

@app.route('/clear-handlers/<uid>', methods=['POST'])
@login_required
def clear_handlers(uid):
    config = db.session.scalars(
        select(Configuration)
        .where(Configuration.uid == uid, Configuration.user_id == current_user.id)
    ).first()
    
    if config:
        config.nodes_handlers = ""
        config.nodes_handlers_meta = {}

        db.session.commit()
        flash(_('Handlers cleared'), 'success')
    active_tab = request.form.get("active_tab", "config")
    return redirect(url_for('edit_config', uid=uid,tab=active_tab))
''
@app.route('/download-handlers/<uid>', methods=['GET'])
@login_required
def download_handlers(uid):
    config = db.session.scalars(
        select(Configuration)
        .where(Configuration.uid == uid, Configuration.user_id == current_user.id)
    ).first()
    
    if not config or not config.nodes_handlers:
        abort(404)
    
    try:
        
        file_content = base64.b64decode(config.nodes_handlers)
        
        
        filename = 'handlers.py'
        if config.nodes_handlers_meta:
            if 'filename' in config.nodes_handlers_meta:
                filename = config.nodes_handlers_meta['filename']
            elif 'url' in config.nodes_handlers_meta:
                
                url_path = urlparse(config.nodes_handlers_meta['url']).path
                filename = url_path.split('/')[-1] or 'handlers.py'
        
        
        file_obj = io.BytesIO(file_content)
        file_obj.seek(0)
        
        return send_file(
            file_obj,
            as_attachment=True,
            download_name=filename,
            mimetype='text/x-python'
        )
    
    except Exception as e:
        flash(_('Download error:') +str(e))
        active_tab = request.form.get("active_tab", "config")
        return redirect(url_for('edit_config', uid=uid,tab=active_tab))

#API
@app.route('/api/config/<uid>')
def get_config(uid):
    #import json
    # Access control:
    # - if basic auth provided: require can_api and config access
    # - else if user logged in: require (can_client OR can_designer) and config access
    #auth = request.authorization
    #if auth:
    #    user = check_api_auth(auth.username, auth.password)
    #    if not user or not bool(getattr(user, 'can_api', False)) or not user_can_access_config(user, uid):
    #        return jsonify({'error': 'Forbidden'}), 403
    #else:
    #    if not getattr(current_user, 'is_authenticated', False):
    #        return jsonify({'error': 'Unauthorized'}), 401
    #    if not (bool(getattr(current_user, 'can_client', False)) or bool(getattr(current_user, 'can_designer', False))):
    #        return jsonify({'error': 'Forbidden'}), 403
    #    if not user_can_access_config(current_user, uid) and not db.session.execute(select(Configuration).where(Configuration.uid==uid, Configuration.user_id==current_user.id)).scalar_one_or_none():
    #        return jsonify({'error': 'Forbidden'}), 403

    config = db.session.execute(
        select(Configuration).where(Configuration.uid == uid)
    ).scalar_one_or_none()

    if not config:
        abort(404)
    
    provider = (config.user.config_display_name 
               if config.user and hasattr(config.user, 'config_display_name') 
               else (config.user.email if config.user else 'Unknown'))
    
    local_time = config.last_modified.astimezone(g.user_timezone)

    base_url = url_for('get_config', uid=config.uid, _external=True)
    
    return json.dumps({
        'name': config.name,
        'server_name': config.server_name,
        'uid': config.uid,
        'url':base_url,
        "content_uid": config.content_uid,
        'nodes_handlers': config.nodes_handlers,
        'version': getattr(config, 'version', '00.00.01'),
        'last_modified': local_time.isoformat(),
        "NodaLogicFormat": NL_FORMAT,
        "NodaLogicType": "ANDROID_SERVER",
        'provider': config.vendor,
        'classes': [
            {
                'name': c.name,
                'section': c.section,
                'section_code': c.section_code,
                'has_storage': c.has_storage,
                'display_name': c.display_name,
                'cover_image': c.cover_image,
                'display_image_web': getattr(c, 'display_image_web', '') or '',
                'display_image_table': getattr(c, 'display_image_table', '') or '',
                'init_screen_layout': getattr(c, 'init_screen_layout', '') or '',

                'commands': getattr(c, 'commands', '') or '',
                'use_standard_commands': bool(getattr(c, 'use_standard_commands', True)),
                'svg_commands': getattr(c, 'svg_commands', '') or '',
                # Migration tab
                'migration_register_command': bool(getattr(c, 'migration_register_command', False)),
                'migration_register_on_save': bool(getattr(c, 'migration_register_on_save', False)),
                'migration_default_room_uid': getattr(c, 'migration_default_room_uid', '') or '',
                'migration_default_room_alias': getattr(c, 'migration_default_room_alias', '') or '',
                'class_type': c.class_type,
                'hidden': c.hidden,
                'methods': [{
                    'name': m.name,
                    'source': m.source,
                    'engine': m.engine,
                    'code': m.code
                } for m in c.methods],
                'events': [
                    {
                        'event': e.event,
                        'listener': e.listener,
                        'actions': [
                            {
                                'action': a.action,
                                'source': a.source,
                                'server': a.server,
                                'method': a.method,
                                'postExecuteMethod': a.post_execute_method
                            }
                            for a in e.actions
                        ]
                    }
                    for e in c.event_objs
                ]
            } for c in config.classes
        ],
        'datasets': [
            {
                'name': d.name,
                'hash_indexes': d.hash_indexes.split(',') if d.hash_indexes else [],
                'text_indexes': d.text_indexes.split(',') if d.text_indexes else [],
                'view_template': d.view_template,
                'autoload': d.autoload,
                'created_at': d.created_at.isoformat(),
                'updated_at': d.updated_at.isoformat(),
                'api_url':f"{base_url}/dataset/{d.name}/items",
                'item_count': len(d.items)
            } for d in config.datasets
        ],
        'sections': [
            {
                'name': d.name,
                'code': d.code,
                'commands': d.commands
            } for d in config.sections
        ],
        "servers": [
            {"alias": s.alias, "url": s.url, "is_default": s.is_default}
            for s in config.servers
        ],
        "rooms": [
            {"alias": ra.alias, "room_id": ra.room_uid}
            for ra in (getattr(config, 'room_aliases', None) or [])
        ],
        'CommonEvents': [
            {
                'event': e.event,
                'listener': e.listener,
                'actions': [
                    {
                        'action': a.action,
                        'source': a.source,
                        'server': a.server,
                        'method': a.method,
                        'postExecuteMethod': a.post_execute_method
                    }
                    for a in e.actions
                ]
            }
            for e in config.config_events
        ]
    }, ensure_ascii=False, indent=4)

def method_exists_in_code(module_code, class_name, method_name):
    
    try:
        tree = ast.parse(module_code)
        
        for node in ast.walk(tree):
            if (isinstance(node, ast.ClassDef) and 
                node.name == class_name):
                
                for class_node in node.body:
                    if (isinstance(class_node, ast.FunctionDef) and 
                        class_node.name == method_name):
                        return True
        return False
    except Exception as e:
        print(f"Error checking method existence: {str(e)}")
        return False
    



@app.route('/get-config-methods')
def get_config_methods():
    config_uid = request.args.get('config_uid')
    config = Configuration.query.filter_by(uid=config_uid).first()

    if not config:
        return jsonify({"methods": []})

    methods = []

    # Android handlers
    try:
        methods.extend(extract_functions_from_handlers(getattr(config, "nodes_handlers", None)))
    except Exception:
        pass

    # Server handlers (Handlers/<uid>/handlers.py)
    try:
        methods.extend(extract_functions_from_handlers(getattr(config, "nodes_server_handlers", None)))
    except Exception:
        pass

    # unique + sorted
    methods = sorted({m for m in methods if m})

    return jsonify({"methods": methods})



@app.route('/config/<config_uid>/add-event', methods=['POST'])
@login_required
def add_config_event(config_uid):
    config = Configuration.query.filter_by(uid=config_uid).first()
    if not config or config.user_id != current_user.id:
        return jsonify({"status": "error", "message": "Configuration not found"})
    
    event_name = request.form.get('event_name')
    listener = request.form.get('listener', '')
    actions_json = request.form.get('actions_json', '[]')
    active_tab = request.form.get('active_tab', 'common-events')
    
    try:
        actions = json.loads(actions_json)
    except:
        actions = []
    
    
    existing_event = ConfigEvent.query.filter_by(
        config_id=config.id, 
        event=event_name, 
        listener=listener
    ).first()
    
    if existing_event:
        return jsonify({"status": "error", "message": "Event already exists"})
    
   
    new_event = ConfigEvent(
        event=event_name,
        listener=listener,
        config_id=config.id
    )
    db.session.add(new_event)
    db.session.flush()  
    
    
    for action_data in actions:
        action = ConfigEventAction(
            event_id=new_event.id,
            action=action_data.get('action', 'run'),
            method=action_data.get('method', ''),
            source=action_data.get('source', 'internal'),
            server=action_data.get('server', ''),
            post_execute_method=action_data.get('postExecuteMethod', ''),
            order=action_data.get('order', 0)
        )
        db.session.add(action)
    
    db.session.commit()
    
    return jsonify({
        "status": "success",
        "message": "Event added successfully",
        "redirect_url": url_for('edit_config', uid=config_uid, tab=active_tab)
    })


@app.route('/config/<config_uid>/edit-event', methods=['POST'])
@login_required
def edit_config_event(config_uid):
    config = Configuration.query.filter_by(uid=config_uid).first()
    if not config or config.user_id != current_user.id:
        return jsonify({"status": "error", "message": "Configuration not found"})
    
    old_event_name = request.form.get('old_event_name')
    old_listener = request.form.get('old_listener', '')
    event_name = request.form.get('event_name')
    listener = request.form.get('listener', '')
    actions_json = request.form.get('actions_json', '[]')
    active_tab = request.form.get('active_tab', 'common-events')
    
    try:
        actions = json.loads(actions_json)
    except:
        actions = []
    
    
    event = ConfigEvent.query.filter_by(
        config_id=config.id, 
        event=old_event_name, 
        listener=old_listener
    ).first()
    
    if not event:
        return jsonify({"status": "error", "message": "Event not found"})
    
    
    event.event = event_name
    event.listener = listener
    
    
    ConfigEventAction.query.filter_by(event_id=event.id).delete()
    
    
    for action_data in actions:
        action = ConfigEventAction(
            event_id=event.id,
            action=action_data.get('action', 'run'),
            method=action_data.get('method', ''),
            source=action_data.get('source', 'internal'),
            server=action_data.get('server', ''),
            post_execute_method=action_data.get('postExecuteMethod', ''),
            order=action_data.get('order', 0)
        )
        db.session.add(action)
    
    db.session.commit()
    
    return jsonify({
        "status": "success", 
        "message": "Event updated successfully",
        "redirect_url": url_for('edit_config', uid=config_uid, tab=active_tab)
    })


@app.route('/config/<config_uid>/delete-event', methods=['POST'])
@login_required
def delete_config_event(config_uid):
    config = Configuration.query.filter_by(uid=config_uid).first()
    if not config or config.user_id != current_user.id:
        return jsonify({"status": "error", "message": "Configuration not found"})
    
    event_name = request.form.get('event_name')
    listener = request.form.get('listener', '')
    active_tab = request.form.get('active_tab', 'common-events')
    
    event = ConfigEvent.query.filter_by(
        config_id=config.id, 
        event=event_name, 
        listener=listener
    ).first()
    
    if event:
        db.session.delete(event)
        db.session.commit()
    
    return jsonify({
        "status": "success",
        "message": "Event deleted successfully", 
        "redirect_url": url_for('edit_config', uid=config_uid, tab=active_tab)
    })


@app.route('/get-config-event-json')
def get_config_event_json():
    event_id = request.args.get('event_id')
    event = ConfigEvent.query.get(event_id)
    
    if not event:
        return jsonify({})
    
    return jsonify({
        "event": event.event,
        "listener": event.listener,
        "actions": event.actions_as_dicts()
    })



@app.route('/config/<config_uid>/common-layouts', methods=['POST'])
@login_required
def save_common_layouts(config_uid):
    config = Configuration.query.filter_by(uid=config_uid).first()
    if not config or config.user_id != current_user.id:
        return jsonify({"status": "error", "message": "Configuration not found"}), 404

    layouts = None

    # preferred: JSON from fetch()
    if request.is_json:
        body = request.get_json(silent=True) or {}
        layouts = body.get("common_layouts", None)

    # fallback: form submit style
    if layouts is None:
        raw = request.form.get("common_layouts_json", "")
        if raw:
            try:
                layouts = json.loads(raw)
            except Exception:
                layouts = None

    if not isinstance(layouts, list):
        return jsonify({"status": "error", "message": "common_layouts must be a list"}), 400

    # minimal sanitize (same spirit as your other handlers: don't crash, keep stable)
    cleaned = []
    for it in layouts:
        if not isinstance(it, dict):
            continue
        _id = str(it.get("id", "")).strip()
        if not _id:
            continue
        cleaned.append({
            "id": _id,
            "layout": it.get("layout", [])
        })

    config.common_layouts = cleaned
    db.session.commit()

    return jsonify({
        "status": "success",
        "message": "CommonLayouts saved",
        "redirect_url": url_for('edit_config', uid=config_uid, tab='common_layouts')
    })


def extract_functions_from_handlers(handlers_code):
    
    if not handlers_code:
        return []
    
    
    handlers_code = base64.b64decode(handlers_code).decode('utf-8')
    
    
    functions = []
    
    
    lines = handlers_code.split('\n')
    in_class = False
    class_indent_level = 0
    
    for line in lines:
        stripped = line.strip()
        
        
        if not stripped or stripped.startswith('#'):
            continue
            
        
        indent_level = len(line) - len(line.lstrip())
        
        
        if stripped.startswith('class '):
            in_class = True
            class_indent_level = indent_level
            continue
            
        
        if in_class and indent_level <= class_indent_level and not stripped.startswith('class '):
            in_class = False
            
        
        if not in_class and stripped.startswith('def '):
            
            match = re.match(r'def\s+(\w+)\s*\(', stripped)
            if match:
                func_name = match.group(1)
                
                if not func_name.startswith('__') or func_name == '__init__':
                    functions.append(func_name)
    
    return sorted(list(set(functions)))

@app.route('/edit-config/<uid>', methods=['GET', 'POST'])
@login_required
def edit_config(uid):
    config = db.session.scalars(
        select(Configuration)
        .where(Configuration.uid == uid, Configuration.user_id == current_user.id)
    ).first()
    
    if not config:
        abort(404)

     
    if request.method == 'GET':
        sync_classes_from_server_handlers(config)
        sync_classes_from_android_handlers(config)
        sync_methods_from_code(config)  
        db.session.refresh(config) 

    edit_dataset = None
    if request.args.get('edit_dataset'):
        edit_dataset = db.session.get(Dataset, request.args.get('edit_dataset'))
        if not edit_dataset or edit_dataset.config_id != config.id:
            abort(404)    
    
    if request.method == 'POST':

        raw = request.form.get("common_layouts_json", "")
        if raw:
            try:
                config.common_layouts = json.loads(raw)
            except Exception:
                pass
        config.name = request.form.get('name')
        config.server_name = request.form.get('server_name')
        db.session.commit()
        flash(_('Configuration saved'), 'success')
        return redirect(url_for('dashboard'))
    
    rooms = Room.query.filter_by(user_id=current_user.id).order_by(Room.name.asc()).all()
    ui_tpl_buttons, ui_tpl_map = get_ui_component_templates()
    return render_template('edit_config.html',
                           config=config,
                           base64=base64,
                           rooms=rooms,
                           ui_tpl_buttons=ui_tpl_buttons,
                           ui_tpl_map=ui_tpl_map)


@app.route('/add-class/<config_uid>', methods=['POST'])
@login_required
def add_class(config_uid):
    config = db.session.execute(
        select(Configuration)
        .where(Configuration.uid == config_uid, Configuration.user_id == current_user.id)
    ).scalar_one_or_none()
    
    name = request.form.get('name')
    if name:
        new_class = ConfigClass(name=name, config_id=config.id)
        db.session.add(new_class)
        db.session.commit()
    active_tab = request.form.get("active_tab", "config")
    return redirect(url_for('edit_config', uid=config_uid, tab=active_tab))

def remove_class_from_module(module_code: str, class_name: str) -> str:
    lines = module_code.split('\n')

    class_start = -1
    class_indent = 0

    # найти строку "class ClassName("
    for i, line in enumerate(lines):
        if line.strip().startswith(f'class {class_name}('):
            class_start = i
            class_indent = len(line) - len(line.lstrip())
            break

    if class_start == -1:
        return module_code  # класс не найден — ничего не меняем

    # найти конец класса: первая НЕ пустая строка с indent <= class_indent
    class_end = len(lines)
    for i in range(class_start + 1, len(lines)):
        cur = lines[i]
        if not cur.strip():
            continue
        cur_indent = len(cur) - len(cur.lstrip())
        if cur_indent <= class_indent:
            class_end = i
            break

    new_lines = lines[:class_start] + lines[class_end:]
    return '\n'.join(new_lines)


@app.route('/delete-class/<class_id>')
@login_required
def delete_class(class_id):
    active_tab = request.args.get("tab", "classes")
    class_obj = db.session.get(ConfigClass, class_id)
    if not class_obj:
        abort(404)

    cfg = class_obj.config
    config_uid = cfg.uid
    class_name = class_obj.name

    try:
        # ANDROID handlers
        if cfg.nodes_handlers:
            android_code = base64.b64decode(cfg.nodes_handlers).decode("utf-8", errors="replace")
            android_code2 = remove_class_from_module(android_code, class_name)
            if android_code2 != android_code:
                cfg.nodes_handlers = base64.b64encode(android_code2.encode("utf-8")).decode("utf-8")

        # SERVER handlers
        if cfg.nodes_server_handlers:
            server_code = base64.b64decode(cfg.nodes_server_handlers).decode("utf-8", errors="replace")
            server_code2 = remove_class_from_module(server_code, class_name)
            if server_code2 != server_code:
                cfg.nodes_server_handlers = base64.b64encode(server_code2.encode("utf-8")).decode("utf-8")

                handlers_dir = os.path.join('Handlers', cfg.uid)
                os.makedirs(handlers_dir, exist_ok=True)
                with open(os.path.join(handlers_dir, 'handlers.py'), 'w', encoding='utf-8') as f:
                    f.write(server_code2)

        # теперь можно удалять из БД
        db.session.delete(class_obj)

        cfg.update_last_modified()
        db.session.commit()

    except Exception as e:
        db.session.rollback()
        flash(f"Delete class error: {e}", "danger")

    return redirect(url_for('edit_config', uid=config_uid, tab=active_tab))



@app.route('/edit-class/<int:class_id>', methods=['GET', 'POST'])
@login_required
def edit_class(class_id):
    class_obj = db.session.get(ConfigClass, class_id)
    if not class_obj:
        abort(404)
    
    
    if class_obj.config.user_id != current_user.id:
        abort(403)
    
    if request.method == 'POST':
        class_obj.name = request.form.get('name')
        # Display tab
        class_obj.display_name = request.form.get('display_name')
        class_obj.cover_image = request.form.get('cover_image')
        class_obj.display_image_web = request.form.get('display_image_web')
        class_obj.display_image_table = request.form.get('display_image_table')
        class_obj.init_screen_layout = request.form.get('init_screen_layout') or ""

        # Commands tab/group
        class_obj.commands = request.form.get('commands')
        class_obj.use_standard_commands = 'use_standard_commands' in request.form
        class_obj.svg_commands = request.form.get('svg_commands')

        # Migration tab
        class_obj.migration_register_command = 'migration_register_command' in request.form
        class_obj.migration_register_on_save = 'migration_register_on_save' in request.form
        class_obj.migration_default_room_alias = (request.form.get('migration_default_room_alias') or '').strip()
        # Backward compatibility: keep old UID if it's still posted
        if 'migration_default_room_uid' in request.form:
            class_obj.migration_default_room_uid = (request.form.get('migration_default_room_uid') or '').strip()

        class_obj.has_storage = 'has_storage' in request.form
        class_obj.class_type = request.form.get('class_type')
        class_obj.hidden = 'hidden' in request.form 

        section_code = request.form.get('section_code')
        

        section_name = ""
        if section_code:
            section = next((s for s in class_obj.config.sections if s.code == section_code), None)
            if section:
                section_name = section.name

        class_obj.section = section_name
        class_obj.section_code = section_code
        db.session.commit()
        flash(_('Class saved'), 'success')
        active_tab = request.form.get("active_tab", "config")
        return redirect(url_for('edit_config', uid=class_obj.config.uid, tab=active_tab))

    rooms = Room.query.filter_by(user_id=current_user.id).order_by(Room.name.asc()).all()
    room_aliases = RoomAlias.query.filter_by(config_id=class_obj.config_id).order_by(RoomAlias.alias.asc()).all()

    ui_tpl_buttons, ui_tpl_map = get_ui_component_templates()

    return render_template('edit_class.html',
                         class_obj=class_obj,
                         rooms=rooms,
                         room_aliases=room_aliases,
                         ui_tpl_buttons=ui_tpl_buttons,
                         ui_tpl_map=ui_tpl_map,
                         event_types=['onShow', 'onInput', 'onChange', 'onShowWeb', 'onInputWeb',"onAcceptServer"])


@app.route('/add-method/<int:class_id>', methods=['POST'])
@login_required
def add_method(class_id):
    class_obj = db.session.get(ConfigClass, class_id)
    if not class_obj:
        abort(404)

    method_name = request.form['name']    
    
    new_method = ClassMethod(
        name=method_name,
        source='internal',
        engine=request.form['engine'],
        code=method_name,
        class_id=class_id
    )
    
    function_body = request.form.get('function_body', '')
    
    
    if new_method.engine == 'server_python':
        current_module = ""
        if class_obj.config.nodes_server_handlers:
            current_module = base64.b64decode(class_obj.config.nodes_server_handlers).decode('utf-8')
        
        
        new_module = add_method_to_class(current_module, class_obj.name, new_method.code, function_body)
        if new_module!=None:
            
            class_obj.config.nodes_server_handlers = base64.b64encode(new_module.encode('utf-8')).decode('utf-8')
            
            
            handlers_dir = os.path.join('Handlers', class_obj.config.uid)
            os.makedirs(handlers_dir, exist_ok=True)
            handlers_file_path = os.path.join(handlers_dir, 'handlers.py')
            with open(handlers_file_path, 'w', encoding='utf-8') as f:
                f.write(new_module)
    
    
    elif new_method.engine == 'android_python':
        current_module = ""
        if class_obj.config.nodes_handlers:
            current_module = base64.b64decode(class_obj.config.nodes_handlers).decode('utf-8')
        
        
        new_module = add_method_to_class(current_module, class_obj.name, new_method.code, function_body)
        
       
        if new_module!=None:
            class_obj.config.nodes_handlers = base64.b64encode(new_module.encode('utf-8')).decode('utf-8')
    
    db.session.add(new_method)
    db.session.commit()
    
    
    exclude_methods = [(class_obj.name, new_method.code)]
    sync_methods_from_code(class_obj.config, exclude_methods)
    
    return redirect(url_for('edit_class', class_id=class_id, _anchor='handlers-refresh'))



@app.route('/delete-method/<int:method_id>')
@login_required
def delete_method(method_id):
    method = db.session.get(ClassMethod, method_id)
    if not method:
        abort(404)
    
    class_id = method.class_id
    config = method.class_obj.config

    class_name = method.class_obj.name
    method_name = method.code
    engine = method.engine

    db.session.delete(method)
    db.session.commit()

    remove_method_from_code(config, class_name, method_name, engine)

    return redirect(url_for('edit_class', class_id=class_id))


@app.route('/edit-method/<int:method_id>', methods=['GET', 'POST'])
@login_required
def edit_method(method_id):
    method = db.session.get(ClassMethod, method_id)
    if not method:
        abort(404)
    
    
    if method.class_obj.config.user_id != current_user.id:
        abort(403)
    
    if request.method == 'POST':
        method.name = request.form['name']
        method.source = request.form['source']
        method.engine = request.form['engine']
        method.code = request.form['code']
        db.session.commit()
        flash(_('Method updated successfully'), 'success')
        return redirect(url_for('edit_class', class_id=method.class_id))
    
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'name': method.name,
            'source': method.source,
            'engine': method.engine,
            'code': method.code
        })
    
    return render_template('edit_method.html', method=method)




@app.route('/add-event/<int:class_id>', methods=['POST'])
@login_required
def add_event(class_id):
    class_obj = db.session.get(ConfigClass, class_id)
    if not class_obj or class_obj.config.user_id != current_user.id:
        abort(403)

    event_name = request.form.get('event_name','').strip()
    listener = request.form.get('listener','').strip()

    actions_json = request.form.get('actions_json')
    try:
        actions = json.loads(actions_json) if actions_json else []
    except Exception:
        flash(_('Invalid actions format (JSON)'), 'error')
        return redirect(url_for('edit_class', class_id=class_id, _anchor='events'))

    if not event_name or not isinstance(actions, list) or len(actions)==0:
        flash(_('Event type and at least one action required'), 'error')
        return redirect(url_for('edit_class', class_id=class_id, _anchor='events'))

    
    for a in actions:
        mname = a.get('method','').strip()
        if mname:
            m = db.session.execute(
                select(ClassMethod).where(ClassMethod.name == mname, ClassMethod.class_id == class_id)
            ).scalar_one_or_none()
            if not m:
                flash(_('Method')+ mname+_(' not found in class'), 'error')
                return redirect(url_for('edit_class', class_id=class_id, _anchor='events'))

    
    existing = db.session.scalars(
    select(ClassEvent).where(ClassEvent.class_id==class_id, 
                            ClassEvent.event==event_name, 
                            ClassEvent.listener==listener)
    .limit(1)
    ).first()
    if existing:
        flash(_('Event with this event+listener already exists'), 'error')
        return redirect(url_for('edit_class', class_id=class_id, _anchor='events'))

    ce = ClassEvent(event=event_name, listener=listener, class_id=class_id)
    db.session.add(ce)
    db.session.flush()  

    order = 0
    for a in actions:
        order += 1
        ea = EventAction(
            action = a.get('action','run'),
            source = a.get('source','internal') or 'internal',
            server = a.get('server','') or '',
            method = a.get('method','') or '',
            post_execute_method = a.get('postExecuteMethod','') or '',
            order = order,
            event_id = ce.id
        )
        db.session.add(ea)

    db.session.commit()
    flash(_('Event added'), 'success')
    return redirect(url_for('edit_class', class_id=class_id, _anchor='events'))


@app.route('/edit-event/<int:class_id>', methods=['POST'])
@login_required
def edit_event(class_id):
    class_obj = db.session.get(ConfigClass, class_id)
    if not class_obj or class_obj.config.user_id != current_user.id:
        abort(403)

    old_event = request.form.get('old_event_name','')
    old_listener = request.form.get('old_listener','')

    # find target event
    target = db.session.execute(
        select(ClassEvent).where(ClassEvent.class_id==class_id,
                                 ClassEvent.event==old_event,
                                 ClassEvent.listener==old_listener)
    ).scalar_one_or_none()

    if not target:
        flash(_('Original event not found'), 'error')
        return redirect(url_for('edit_class', class_id=class_id, _anchor='events'))

    new_event = request.form.get('event_name','').strip()
    new_listener = request.form.get('listener','').strip()
    actions_json = request.form.get('actions_json')
    try:
        actions = json.loads(actions_json) if actions_json else []
    except Exception:
        flash(_('Invalid actions format (JSON)'), 'error')

        return redirect(url_for('edit_class', class_id=class_id, _anchor='events'))

    if not new_event or not isinstance(actions, list) or len(actions)==0:
        flash(_('Event type and at least one action required'), 'error')
        return redirect(url_for('edit_class', class_id=class_id, _anchor='events'))

    
    for a in actions:
        mname = a.get('method','').strip()
        if mname:
            m = db.session.execute(
                select(ClassMethod).where(ClassMethod.name == mname, ClassMethod.class_id == class_id)
            ).first()
            if not m:
                flash(_('Method %(mname)s not found in class', mname=mname), 'error')
                return redirect(url_for('edit_class', class_id=class_id, _anchor='events'))

    
    target.event = new_event
    target.listener = new_listener

    
    for act in list(target.actions):
        db.session.delete(act)
    db.session.flush()

    order = 0
    for a in actions:
        order += 1
        ea = EventAction(
            action = a.get('action','run'),
            source = a.get('source','internal') or 'internal',
            server = a.get('server','') or '',
            method = a.get('method','') or '',
            post_execute_method = a.get('postExecuteMethod','') or '',
            order = order,
            event_id = target.id
        )
        db.session.add(ea)

    db.session.commit()
    flash(_('Event updated'), 'success')
    return redirect(url_for('edit_class', class_id=class_id, _anchor='events'))


@app.route('/delete-event/<int:class_id>', methods=['POST'])
@login_required
def delete_event(class_id):
    class_obj = db.session.get(ConfigClass, class_id)
    if not class_obj or class_obj.config.user_id != current_user.id:
        abort(403)

    event_name = request.form.get('event_name','')
    listener = request.form.get('listener','').strip()

    target = db.session.execute(
        select(ClassEvent).where(ClassEvent.class_id==class_id,
                                 ClassEvent.event==event_name,
                                 ClassEvent.listener==listener)
    ).scalar_one_or_none()

    if not target:
        flash(_('Event not found'), 'error')
        return redirect(url_for('edit_class', class_id=class_id, _anchor='events'))

    db.session.delete(target)
    db.session.commit()
    flash(_('Event deleted'), 'success')
    return redirect(url_for('edit_class', class_id=class_id, _anchor='events'))



@app.route('/create-config', methods=['POST'])
@login_required
def create_config():
    
    new_config = Configuration(
    name=_("New configuration"),
    user_id=current_user.id,
    content_uid=str(uuid.uuid4()),
    vendor=current_user.config_display_name or current_user.email,
    version="00.00.01"
)

    new_config.uid = str(uuid.uuid4())

    
    android_imports = ANDROID_IMPORTS_TEMPLATE.format(
        uid=new_config.uid, 
        config_url=url_for('get_config', uid=new_config.uid, _external=True)
    )
    default_handlers = android_imports + NODE_CLASS_CODE_ANDROID 
    new_config.nodes_handlers = base64.b64encode(default_handlers.encode('utf-8')).decode('utf-8')

    
    default_server_handlers = NODE_CLASS_CODE 
    new_config.nodes_server_handlers = base64.b64encode(default_server_handlers.encode('utf-8')).decode('utf-8')

    db.session.add(new_config)
    db.session.commit()

    
    handlers_dir = os.path.join('Handlers', new_config.uid)
    os.makedirs(handlers_dir, exist_ok=True)
    
    
    handlers_file_path = os.path.join(handlers_dir, 'handlers.py')
    with open(handlers_file_path, 'w', encoding='utf-8') as f:
        f.write(default_server_handlers)
    active_tab = request.form.get("active_tab", "config")
    return redirect(url_for('edit_config', uid=new_config.uid, tab=active_tab))




@app.route('/create-class/<config_uid>', methods=['POST'])
@login_required
def create_class(config_uid):
    config = db.session.scalars(
        select(Configuration)
        .where(Configuration.uid == config_uid, Configuration.user_id == current_user.id)
    ).first()
    
    if not config:
        abort(404)
    
    
    class_name = request.form.get('name')
    if not class_name:
        flash(_('Class name not specified'), 'danger')
        active_tab = request.form.get("active_tab", "config")
        return redirect(url_for('edit_config', uid=config_uid, tab=active_tab))
    
   
    import re
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', class_name):
        flash(_('Class name must start with a letter or underscore and contain only letters, numbers and underscores'), 'error')
        active_tab = request.form.get("active_tab", "config")
        return redirect(url_for('edit_config', uid=config_uid, tab=active_tab))
    
    
    existing_class = next((c for c in config.classes if c.name == class_name), None)
    if existing_class:
        flash(_('Class with this name already exists'), 'danger')
        active_tab = request.form.get("active_tab", "config")
        return redirect(url_for('edit_config', uid=config_uid, tab=active_tab))
    
    
    new_class = ConfigClass(
        name=class_name,
        display_name=class_name,
        config_id=config.id,
        class_type='custom_process',
        section_code='server'
    )
    db.session.add(new_class)
    db.session.commit()
    
    
    if config.nodes_server_handlers:
        try:
            current_code = base64.b64decode(config.nodes_server_handlers).decode('utf-8')
            
            
            if 'from nodes import Node' not in current_code:
                current_code = NODE_CLASS_CODE + '\n\n' + current_code
            
            
            new_class_code = f'''
class {class_name}(Node):
    
    def __init__(self, node_id=None, config_uid=None):
        super().__init__(node_id, config_uid)
        # Additional initialozation for {class_name}
'''
            current_code += '\n\n' + new_class_code
            
            
            config.nodes_server_handlers = base64.b64encode(current_code.encode('utf-8')).decode('utf-8')
            
            
            handlers_dir = os.path.join('Handlers', config.uid)
            os.makedirs(handlers_dir, exist_ok=True)
            handlers_file_path = os.path.join(handlers_dir, 'handlers.py')
            with open(handlers_file_path, 'w', encoding='utf-8') as f:
                f.write(current_code)
                
        except Exception as e:
            print(f"Error updating server handlers: {str(e)}")
    
    
    if config.nodes_handlers:
        try:
            current_code = base64.b64decode(config.nodes_handlers).decode('utf-8')
            
            
            if 'from nodes import Node' not in current_code:
                current_code = NODE_CLASS_CODE_ANDROID + '\n' + current_code
            
            
            new_class_code = f'''
class {class_name}(Node):
    def __init__(self, modules, jNode, modulename, uid, _data):
        super().__init__(modules, jNode, modulename, uid, _data)

    """Class {class_name}"""
'''
            current_code += '\n\n' + new_class_code
            
            
            config.nodes_handlers = base64.b64encode(current_code.encode('utf-8')).decode('utf-8')
                
        except Exception as e:

            print(f"Error updating android handlers: {str(e)}")
    
    db.session.commit()
    flash(_('Class created successfully'), 'success')
    active_tab = request.form.get("active_tab", "config")
    return redirect(url_for('edit_class', class_id=new_class.id, tab=active_tab))


def _build_runtime_parsed_config(config: Configuration) -> dict:
    """Build minimal parsed config dict needed for class events dispatch."""
    classes = {}
    try:
        for c in (config.classes or []):
            events = []
            event_objs = getattr(c, "event_objs", None) or getattr(c, "events", None) or []
            for e in (event_objs or []):
                actions = []
                for a in (getattr(e, "actions", None) or []):
                    actions.append({
                        "action": getattr(a, "action", ""),
                        "source": getattr(a, "source", ""),
                        "server": getattr(a, "server", None),
                        "method": getattr(a, "method", ""),
                        "postExecuteMethod": getattr(a, "post_execute_method", "") or getattr(a, "postExecuteMethod", ""),
                    })
                events.append({
                    "event": getattr(e, "event", ""),
                    "listener": getattr(e, "listener", "") or "",
                    "actions": actions,
                })
            classes[getattr(c, "name", "")] = {"events": events}
    except Exception:
        pass
    return {"classes": classes}

@app.route('/api/config/<config_uid>/node/<class_name>/<node_id>/<method_name>', methods=['POST'])
@api_auth_required
def execute_node_method(config_uid, class_name, node_id, method_name):
    """API for node execution"""
    config = db.session.execute(
        select(Configuration).where(Configuration.uid == config_uid)
    ).scalar_one_or_none()
    
    if not config:
        abort(404)
    runtime_parsed = _build_runtime_parsed_config(config)
    _ctx_tokens = _nodes_mod.set_runtime_context(config_uid, runtime_parsed)

    @after_this_request
    def _reset_ctx(resp):
        _nodes_mod.reset_runtime_context(_ctx_tokens)
        return resp

    
    try:
        if os.path.isfile(_handlers_file_path(config_uid)) or config.nodes_server_handlers:
            isolated_globals = _load_server_handlers_ns(config_uid, config)
            
            # Check that the class exists and is a subclass of Node
            if (class_name in isolated_globals and 
                hasattr(isolated_globals[class_name], '__bases__') and
                any(base.__name__ == 'Node' for base in isolated_globals[class_name].__bases__)):
                
                node_class = isolated_globals[class_name]
                
                # Get the node
                node = node_class.get(node_id, config_uid)
                if not node:
                    abort(404, description=f"Node {node_id} not found")
                
                # Check the existence of the method
                if not hasattr(node, method_name):
                    abort(404, description=f"Method {method_name} not found in class {class_name}")
                
                # Getting input data
                request_data = request.get_json() or {}
                
                # Determine the method type
                custom_methods = ['_sum_transaction', '_get_sum_balance', '_get_balance', '_get_sum_transactions',
            '_state_transaction', '_get_state_balance', '_get_state_transactions',
            '_add_scheme', '_remove_scheme']
                
                if method_name in custom_methods:
                    # Handling arbitrary methods
                    args = request_data.get('args', [])
                    kwargs = request_data.get('kwargs', {})
                    
                    try:
                        result = getattr(node, method_name)(*args, **kwargs)
                        return jsonify({
                            'status': True,
                            'result': result
                        })
                    except _nodes_mod.AcceptRejected as e:

                        return jsonify({'status': False, 'data': e.payload}), 200

                    except Exception as e:
                        return jsonify({
                            'status': False,
                            'error': str(e)
                        }), 500
                
                else:
                    # Processing standard methods
                    input_data = request_data
                    
                    try:
                        if method_name == "_save":
                            if input_data:
                                node._data_cache = input_data
                            result = node._save()

                            return jsonify({
                                'status': result,
                                'node': node.to_dict()
                            })
                        else:
                            result = getattr(node, method_name)(input_data)
                            if isinstance(result, tuple) and len(result) == 2:

                                success, data = result
                                if hasattr(node, "_ui_layout") and node._ui_layout is not None:
                                    data["_ui_layout"] = node._ui_layout

                                return jsonify({'status': success, 'data': data})
                            else:
                                return jsonify(result)
                    except Exception as e:
                        return jsonify({
                            'status': False,
                            'error': str(e),
                            'node': node.to_dict()
                        }), 500
        
        abort(404, description=f"Class {class_name} not found")
        
    except Exception as e:
        return jsonify({'status': False, "error": str(e)}), 500

#API for calling remote nodes
@app.route('/api/<room_uid>/<target_user>/<config_uid>/remote_node/<class_name>/<node_id>/<method_name>', methods=['POST'])
def execute_remote_method(room_uid, target_user, config_uid, class_name, node_id, method_name):
    """Executing a method on a remote device via WebSocket"""
    
    # Check if the target user is active in the room
    if (room_uid not in active_connections or 
        target_user not in active_connections[room_uid]):
        return jsonify({
            'success': False,
            'error': f'A user {target_user} not in the room {room_uid}'
        }), 404
    
    # Get the target user's WebSocket connection
    target_ws = active_connections[room_uid][target_user]
    if target_ws.closed:
        return jsonify({
            'success': False,
            'error': f'Connection with {target_user} was closed'
        }), 404
    
    # Generate a unique request ID
    request_id = str(uuid.uuid4())
    
    # Getting input data
    input_data = request.get_json() or {}
    
    # Create a message to send
    message = {
        'type': 'remote_method',
        'request_id': request_id,
        'config_uid': config_uid,
        'class_name': class_name,
        'node_id': node_id,
        'method_name': method_name,
        'input_data': input_data,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }
    
    # Initialize the query in the waiting dictionary
    if room_uid not in pending_remote_requests:
        pending_remote_requests[room_uid] = {}
    
    pending_remote_requests[room_uid][request_id] = {
        'result': None,
        'error': None,
        'completed': False
    }
    
    
        
    request_id = str(uuid.uuid4())
    
    # Create a record about waiting for a response
    pending_responses[request_id] = {
        'room_uid': room_uid,
        'completed': False,
        'result': None,
        'error': None,
        'created_at': time.time()
    }
    
    # Add request_id to the message
    message['request_id'] = request_id
    
    try:
        target_ws.send(json.dumps(message))
        
        
        return jsonify({
            'success': True,
            'request_id': request_id,
            'status': 'pending',
            'message': 'The request has been sent. Use /api/check-response to check the status.'
        }), 202
        
    except WebSocketError as e:
        # Remove from pending on error
        if request_id in pending_responses:
            del pending_responses[request_id]
        return jsonify({
            'success': False,
            'error': f'WebSocket Error: {str(e)}'
        }), 500
        


@app.route('/api/check-response/<request_id>')
@api_auth_required
def check_response(request_id):
    """Checking the status of a remote request"""
    if request_id not in pending_responses:
        return jsonify({
            'status': 'not_found',
            'message': 'Request not found or expired'
        }), 404
    
    response_data = pending_responses[request_id]
    
    if response_data['completed']:
        # The request is complete, we return the result and clean up
        result = response_data
        del pending_responses[request_id]
        
        if result['error']:
            return jsonify({
                'status': 'error',
                'error': result['error']
            }), 500
        else:
            return jsonify({
                'status': 'completed',
                'data': result['result']
            })
    else:
        # The request is still in process
        elapsed = time.time() - response_data['created_at']
        return jsonify({
            'status': 'pending',
            'elapsed_seconds': round(elapsed, 1),
            'message': 'The request is still being processed.'
        })

@app.route('/api/config/<config_uid>/node/<class_name>/<node_id>', methods=['GET', 'PUT', 'DELETE'])
@api_auth_required
def node_api(config_uid, class_name, node_id):
    """API for working with a specific node"""
    config = db.session.execute(
        select(Configuration).where(Configuration.uid == config_uid)
    ).scalar_one_or_none()
    
    if not config:
        abort(404)
    runtime_parsed = _build_runtime_parsed_config(config)
    _ctx_tokens = _nodes_mod.set_runtime_context(config_uid, runtime_parsed)

    @after_this_request
    def _reset_ctx(resp):
        _nodes_mod.reset_runtime_context(_ctx_tokens)
        return resp


    internal_id = extract_internal_id(node_id)    
    
    try:
        if os.path.isfile(_handlers_file_path(config_uid)) or config.nodes_server_handlers:
            isolated_globals = _load_server_handlers_ns(config_uid, config)
            
            # We check that the class exists and is a subclass of Node from this space
            if (class_name in isolated_globals and 
                hasattr(isolated_globals[class_name], '__bases__') and
                any(base.__name__ == 'Node' for base in isolated_globals[class_name].__bases__)):
                
                node_class = isolated_globals[class_name]
                
                if request.method == 'GET':
                    node = node_class.get(internal_id , config_uid)
                    if node:
                        return jsonify(node.to_dict())
                    abort(404)
                
                elif request.method == 'PUT':
                    data = request.get_json()
                    node = node_class(internal_id , config_uid)
                    if data:
                        node.update_data(data)

    
                    return jsonify(node.to_dict())
                
                elif request.method == 'DELETE':
                    node = node_class.get(internal_id , config_uid)
                    if node:
                        node.delete()

                        return jsonify({"status": "deleted"})
                    abort(404)
        
        abort(404)
        
    except _nodes_mod.AcceptRejected as e:

        
        return jsonify({'status': False, 'data': e.payload}), 200

        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/config/<config_uid>/node/<class_name>/register/<room_uid>', methods=['POST'])
@api_auth_required
def register_nodes(config_uid, class_name, room_uid):
    """Registers nodes of the specified class in the download room"""
    config = db.session.execute(
        select(Configuration).where(Configuration.uid == config_uid)
    ).scalar_one_or_none()
    
    if not config:
        abort(404)
    
    try:
        # Safely retrieve JSON from the request body
        node_ids = []
        if request.data:  # Check if there is a request body
            try:
                #request_data = request.get_json() or {}
                node_ids = request.get_json() or []
            except Exception:
                # If the JSON is invalid, we assume that the body is empty.
                node_ids = []
        
        if os.path.isfile(_handlers_file_path(config_uid)) or config.nodes_server_handlers:
            isolated_globals = _load_server_handlers_ns(config_uid, config)
            
            # Checking that the class exists
            if (class_name in isolated_globals and 
                hasattr(isolated_globals[class_name], '__bases__') and
                any(base.__name__ == 'Node' for base in isolated_globals[class_name].__bases__)):
                
                node_class = isolated_globals[class_name]
                
                # We receive nodes
                if node_ids:
                    # We register only selected nodes
                    nodes_data = []
                    for node_id in node_ids:
                        node = node_class.get(node_id, config_uid)
                        if node:
                            node_dict = node.to_dict()
                            #node_dict['_id'] = node_id
                            node_dict = node.to_dict()
                            node_dict['_id'] = node_dict.get('_data', {}).get('_id') or node_id
                            nodes_data.append(node_dict)
                    
                    message = f"Registered {len(nodes_data)} selected nodes"
                else:
                    # Register all class nodes
                    nodes = node_class.get_all(config_uid)
                    nodes_data = []
                    for node_id, node in nodes.items():
                        node_dict = node.to_dict()
                        #node_dict['_id'] = node_id
                        node_dict = node.to_dict()
                        node_dict['_id'] = node_dict.get('_data', {}).get('_id') or node_id
                        nodes_data.append(node_dict)
                    
                    message = f"Registered all {len(nodes_data)} nodes"
                
                # We register in the room
                return  handle_room_objects(config_uid, class_name, room_uid, nodes_data)
                
                
              
                
                
        
        abort(404, description=f"Class {class_name} not found")
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/config/<config_uid>/node/<class_name>', methods=['GET', 'POST'])
@api_auth_required
def nodes_api(config_uid, class_name):
    """API for working with all class nodes"""
    import nodes as _nodes_mod

    config = db.session.execute(
        select(Configuration).where(Configuration.uid == config_uid)
    ).scalar_one_or_none()

    if not config:
        abort(404)

    # --- runtime context for onAcceptServer ---
    runtime_parsed = _build_runtime_parsed_config(config)
    _ctx_tokens = _nodes_mod.set_runtime_context(config_uid, runtime_parsed)

    @after_this_request
    def _reset_ctx(resp):
        _nodes_mod.reset_runtime_context(_ctx_tokens)
        return resp

    room_uid = request.args.get('room')

    try:
        # ============================================================
        # ROOM MODE (special create path)
        # ============================================================
        if room_uid and request.method == 'POST':
            data = request.get_json() or {}

            if not (os.path.isfile(_handlers_file_path(config_uid)) or config.nodes_server_handlers):
                abort(404)

            isolated_globals = _load_server_handlers_ns(config_uid, config)

            if (
                class_name not in isolated_globals or
                not hasattr(isolated_globals[class_name], '__bases__') or
                not any(base.__name__ == 'Node'
                        for base in isolated_globals[class_name].__bases__)
            ):
                abort(404)

            node_class = isolated_globals[class_name]

            objects_data = data if isinstance(data, list) else [data]

            for item_data in objects_data:
                raw_id = item_data.get('_id')
                node_id = extract_internal_id(raw_id) if raw_id else str(uuid.uuid4())

                user_data = dict(item_data)

                node = node_class(node_id, config_uid)
                if user_data:
                    node.update_data(user_data)   # <-- AcceptRejected here

            return handle_room_objects(config_uid, class_name, room_uid, data)

        # ============================================================
        # NORMAL MODE
        # ============================================================
        if not (os.path.isfile(_handlers_file_path(config_uid)) or config.nodes_server_handlers):
            abort(404)

        isolated_globals = _load_server_handlers_ns(config_uid, config)

        if (
            class_name not in isolated_globals or
            not hasattr(isolated_globals[class_name], '__bases__') or
            not any(base.__name__ == 'Node'
                    for base in isolated_globals[class_name].__bases__)
        ):
            abort(404)

        node_class = isolated_globals[class_name]

        # ---------------- GET ----------------
        if request.method == 'GET':
            nodes = node_class.get_all(config_uid)
            result = {node_id: node.to_dict() for node_id, node in nodes.items()}
            return jsonify(result)

        # ---------------- POST ----------------
        if request.method == 'POST':
            data = request.get_json() or {}

            # ----- array -----
            if isinstance(data, list):
                created_nodes = []

                for item_data in data:
                    raw_id = item_data.get('_id')
                    node_id = extract_internal_id(raw_id) if raw_id else str(uuid.uuid4())

                    user_data = dict(item_data)

                    node = node_class(node_id, config_uid)
                    if user_data:
                        node.update_data(user_data)   # <-- AcceptRejected here

                    created_nodes.append(node.to_dict())

                return jsonify(created_nodes), 201

            # ----- single -----
            raw_id = data.get('_id')
            node_id = extract_internal_id(raw_id) if raw_id else str(uuid.uuid4())

            user_data = dict(data)

            node = node_class(node_id, config_uid)
            if user_data:
                node.update_data(user_data)   # <-- AcceptRejected here

            return jsonify(node.to_dict()), 201

        abort(404)

    # ============================================================
    # ACCEPT REJECT (EXPECTED BUSINESS ERROR)
    # ============================================================
    except _nodes_mod.AcceptRejected as e:
        return jsonify({
            'status': False,
            'data': e.payload
        }), 200

    # ============================================================
    # REAL ERROR
    # ============================================================
    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500


@app.route('/api/config/<config_uid>/node/<class_name>/page', methods=['GET'])
@api_auth_required
def nodes_api_page(config_uid, class_name):
    """
    Fast paged nodes list from sqlitedict storage (no exec, no Node instantiation).

    Query:
      offset (int), limit (int), q (str)
    Sorting:
      prefers _data._sort_string_desc, then _data._sort_string, else _id
    Search:
      if q -> substring search in _data values (stringified)
    """
    # validate config exists
    config = db.session.execute(
        select(Configuration).where(Configuration.uid == config_uid)
    ).scalar_one_or_none()
    if not config:
        abort(404)

    import os, sqlite3, pickle

    offset = int(request.args.get("offset", 0) or 0)
    limit = int(request.args.get("limit", 50) or 50)
    q = (request.args.get("q") or "").strip().lower()

    storage_key = f"{class_name}_{config_uid}"
    db_path = os.path.join("node_storage", f"{storage_key}.sqlite")
    if not os.path.exists(db_path):
        return jsonify({"total": 0, "offset": offset, "limit": limit, "items": []})

    # sqlitedict default table name is "unnamed" unless specified
    table = "unnamed"

    def unpack(blob):
        try:
            return pickle.loads(blob)
        except Exception:
            return None

    # FAST PATH: no search -> return page ordered by key, without scanning whole DB
    # (Sorting by _sort_string would require unpickling everything anyway.)
    if not q:
        conn = sqlite3.connect(db_path)
        try:
            cur = conn.cursor()
            # total count
            cur.execute(f"SELECT COUNT(1) FROM {table}")
            total = int(cur.fetchone()[0] or 0)

            # page
            cur.execute(
                f"SELECT value FROM {table} ORDER BY key LIMIT ? OFFSET ?",
                (limit, offset),
            )
            rows = cur.fetchall()

            items = []
            for (val_blob,) in rows:
                obj = unpack(val_blob)
                if obj is not None:
                    items.append(obj)

            return jsonify({"total": total, "offset": offset, "limit": limit, "items": items})
        finally:
            conn.close()

    # SLOW PATH: q present -> scan + filter + sort (pickle prevents SQL filtering)
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(1) FROM {table}")
        total_all = int(cur.fetchone()[0] or 0)

        cur.execute(f"SELECT value FROM {table}")
        rows = cur.fetchall()

        all_items = []
        for (val_blob,) in rows:
            obj = unpack(val_blob)
            if obj is None:
                continue
            all_items.append(obj)

        # filter by q
        def match(item: dict) -> bool:
            data = (item or {}).get("_data") or {}
            for v in data.values():
                try:
                    if q in str(v).lower():
                        return True
                except Exception:
                    pass
            return False

        filtered = [it for it in all_items if match(it)]

        # sort
        def sort_key(item: dict):
            data = (item or {}).get("_data") or {}
            if "_sort_string_desc" in data:
                return str(data.get("_sort_string_desc") or "")
            if "_sort_string" in data:
                return str(data.get("_sort_string") or "")
            return str((item or {}).get("_id") or "")

        # if any item has _sort_string_desc -> sort descending
        has_desc = any("_sort_string_desc" in ((it or {}).get("_data") or {}) for it in filtered)
        filtered.sort(key=sort_key, reverse=bool(has_desc))

        total = len(filtered)
        sliced = filtered[offset: offset + limit]

        return jsonify({"total": total, "offset": offset, "limit": limit, "items": sliced, "total_all": total_all})
    finally:
        conn.close()




def handle_room_objects(config_uid, class_name, room_uid,data):
    """Processing objects across the room"""
    #data = request.get_json() or {}
    
    if not isinstance(data, list):
        data = [data]
    
    # Saving objects to the room database
    room_objects = RoomObjects(
        room_uid=room_uid,
        config_uid=config_uid,
        class_name=class_name,
        objects_data=data,
        expires_at=datetime.now(timezone.utc) ,
        acknowledged_by=[] 
    )
    db.session.add(room_objects)
    db.session.commit()
    
    # We send a message to all connected clients of the room
    send_nodes_update(room_uid)
    
    return jsonify({
        "status": "objects_queued",
        "count": len(data),
        "room_uid": room_uid,
        "object_id": room_objects.id,  # Return the ID of the created object
        "message": "Objects sent to room for client processing"
    }), 202 

def send_objects_update(room_uid, config_uid, class_name, objects_data):
    """Sends an object update to all clients of the room"""
    if room_uid in active_connections:
        message = {
            'type': 'objects_create',
            'config_uid': config_uid,
            'class_name': class_name,
            'objects': objects_data,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        for user, ws in list(active_connections[room_uid].items()):
            try:
                if not ws.closed:
                    ws.send(json.dumps(message))
            except WebSocketError:
                active_connections[room_uid].pop(user, None)
                print(f"Removed dead connection for {user}")

@app.route('/api/room/<room_uid>/objects', methods=['GET'])
@api_auth_required
def get_room_objects(room_uid):
    """Get objects for the room"""
    config_uid = request.args.get('config_uid')
    class_name = request.args.get('class_name')
    since = request.args.get('since')  # Optional: Get objects after the specified date
    
    query = RoomObjects.query.filter_by(room_uid=room_uid)
    
    if config_uid:
        query = query.filter_by(config_uid=config_uid)
    if class_name:
        query = query.filter_by(class_name=class_name)
    if since:
        try:
            since_date = datetime.fromisoformat(since.replace('Z', '+00:00'))
            query = query.filter(RoomObjects.created_at > since_date)
        except ValueError:
            pass
    
    objects = query.order_by(RoomObjects.created_at.desc()).all()
    
    result = []
    for obj in objects:
        result.append({
            'id': obj.id,
            'config_uid': obj.config_uid,
            'class_name': obj.class_name,
            'objects': obj.objects_data,
            'created_at': obj.created_at.isoformat(),
            'expires_at': obj.expires_at.isoformat()
        })
    
    return jsonify(result)

@app.route('/api/room/<room_uid>/objects', methods=['DELETE'])
@api_auth_required
def cleanup_room_objects(room_uid):
    """Delete old objects in the room"""
    older_than = request.args.get('older_than')
    
    if not older_than:
        return jsonify({"error": "Parameter 'older_than' is required"}), 400
    
    try:
        cutoff_date = datetime.fromisoformat(older_than.replace('Z', '+00:00'))
        
        # Delete objects older than the specified date
        deleted_count = RoomObjects.query.filter(
            RoomObjects.room_uid == room_uid,
            RoomObjects.created_at < cutoff_date
        ).delete()
        
        db.session.commit()
        
        return jsonify({
            "status": "success",
            "deleted_count": deleted_count,
            "cutoff_date": cutoff_date.isoformat()
        })
        
    except ValueError:
        return jsonify({"error": "Invalid date format. Use ISO format"}), 400                

@app.route('/api/config/<config_uid>/node/<class_name>/search', methods=['POST'])
@api_auth_required
def search_nodes(config_uid, class_name):
    """API for searching nodes by condition"""
    config = db.session.execute(
        select(Configuration).where(Configuration.uid == config_uid)
    ).scalar_one_or_none()
    
    if not config:
        abort(404)
    
    try:
        if os.path.isfile(_handlers_file_path(config_uid)) or config.nodes_server_handlers:
            isolated_globals = _load_server_handlers_ns(config_uid, config)
            
            # We check that the class exists and is a subclass of Node from this space
            if (class_name in isolated_globals and 
                hasattr(isolated_globals[class_name], '__bases__') and
                any(base.__name__ == 'Node' for base in isolated_globals[class_name].__bases__)):
                
                node_class = isolated_globals[class_name]
                
                # We get the search condition from the request body
                search_condition = request.get_json() or {}
                
                def condition_func(node):
                    node_data = node.to_dict().get('_data', {})
                    for key, value in search_condition.items():
                        if key not in node_data or str(node_data[key]) != str(value):
                            return False
                    return True
                
                # We perform a search
                results = node_class.find(condition_func, config_uid)
                return jsonify({node_id: node.to_dict() for node_id, node in results.items()})
        
        abort(404)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/export-config/<uid>')
@login_required
def export_config(uid):
    config = db.session.execute(
        select(Configuration).where(Configuration.uid == uid, Configuration.user_id == current_user.id)
    ).scalar_one_or_none()
    
    if not config:
        abort(404)
    
    
    provider = (config.user.config_display_name 
               if config.user and hasattr(config.user, 'config_display_name') 
               else (config.user.email if config.user else 'Unknown'))

    
    local_time = config.last_modified.astimezone(pytz.timezone('Europe/Moscow'))

    base_url = url_for('get_config', uid=config.uid, _external=True)
    
    
    config_data = {
        'name': config.name,
        'server_name': config.server_name,
        'uid': config.uid,
        'url':base_url,
        'content_uid': config.content_uid,
        'vendor': config.vendor,
        'nodes_handlers': config.nodes_handlers,
        'nodes_handlers_meta': config.nodes_handlers_meta,
        'nodes_server_handlers': config.nodes_server_handlers,  
        'nodes_server_handlers_meta': config.nodes_server_handlers_meta,  
        'version': getattr(config, 'version', '00.00.01'),
        "NodaLogicFormat": NL_FORMAT,
        "NodaLogicType": "ANDROID_SERVER",
        'last_modified': local_time.isoformat(),
        'provider': provider,
        "CommonLayouts": config.common_layouts or [],
        'classes': [
            {
                'name': c.name,
                'section': c.section,
                'section_code': c.section_code,
                'has_storage': c.has_storage,
                'display_name': c.display_name,
                'cover_image': c.cover_image,
                'class_type': c.class_type,
                'hidden': c.hidden,
                'methods': [{
                    'name': m.name,
                    'source': m.source,
                    'engine': m.engine,
                    'code': m.code
                } for m in c.methods],
                'events': [
                    {
                        'event': e.event,
                        'listener': e.listener,
                        'actions': [
                            {
                                'action': a.action,
                                'source': a.source,
                                'server': a.server,
                                'method': a.method,
                                'postExecuteMethod': a.post_execute_method
                            }
                            for a in e.actions
                        ]
                    }
                    for e in c.event_objs
                ]
            } for c in config.classes
        ],
        'datasets': [
            {
                'name': d.name,
                'hash_indexes': d.hash_indexes.split(',') if d.hash_indexes else [],
                'text_indexes': d.text_indexes.split(',') if d.text_indexes else [],
                'view_template': d.view_template,
                'autoload': d.autoload,
                'created_at': d.created_at.isoformat(),
                'updated_at': d.updated_at.isoformat(),
                'api_url': f"{base_url}/dataset/{d.name}/items",
                'item_count': len(d.items)
            } for d in config.datasets
        ],
        'sections': [
            {
                'name': s.name,
                'code': s.code,
                'commands': s.commands
            } for s in config.sections
        ],
        "servers": [
            {"alias": s.alias, "url": s.url, "is_default": s.is_default}
            for s in config.servers
        ],
        "rooms": [
            {"alias": r.alias, "room_id": r.room_uid}
            for r in (getattr(config, 'room_aliases', None) or [])
        ],
        'CommonEvents': [
            {
                'event': e.event,
                'listener': e.listener,
                'actions': [
                    {
                        'action': a.action,
                        'source': a.source,
                        'server': a.server,
                        'method': a.method,
                        'postExecuteMethod': a.post_execute_method
                    }
                    for a in e.actions
                ]
            }
            for e in config.config_events
        ]
    }
    
    file_obj = io.BytesIO(json.dumps(config_data, ensure_ascii=False, indent=4).encode('utf-8'))
    file_obj.seek(0)
    
    return send_file(
        file_obj,
        as_attachment=True,
        download_name=f'config_{config.name}.nod',
        mimetype='application/json'
    )


def _api_coerce_number(x):
    if isinstance(x, (int, float)):
        return x
    if isinstance(x, str):
        try:
            if "." in x:
                return float(x)
            return int(x)
        except Exception:
            return None
    return None

def _api_like(pattern: str, value: str) -> bool:
    pat = re.escape(pattern).replace(r"\%", ".*")
    return re.fullmatch(pat, value or "", flags=re.IGNORECASE) is not None

def _api_eval_leaf(node_data: dict, leaf: dict) -> bool:
    key = leaf.get("key")
    exp = leaf.get("exp")
    wanted = leaf.get("value")

    actual = (node_data or {}).get(key)

    if exp == "~":
        return _api_like(str(wanted or ""), str(actual or ""))

    a_num = _api_coerce_number(actual)
    w_num = _api_coerce_number(wanted)
    if a_num is not None and w_num is not None and exp in ("<", ">", "=", "!="):
        if exp == "<":
            return a_num < w_num
        if exp == ">":
            return a_num > w_num
        if exp == "=":
            return a_num == w_num
        if exp == "!=":
            return a_num != w_num

    a = str(actual) if actual is not None else ""
    w = str(wanted) if wanted is not None else ""

    if exp == "=":
        return a == w
    if exp == "!=":
        return a != w
    if exp == "<":
        return a < w
    if exp == ">":
        return a > w

    return False

def _api_eval_condition(node_data: dict, cond) -> bool:
    if cond is None:
        return True

    if isinstance(cond, dict):
        if "&&" in cond:
            return all(_api_eval_condition(node_data, c) for c in (cond.get("&&") or []))
        if "||" in cond:
            return any(_api_eval_condition(node_data, c) for c in (cond.get("||") or []))
        if "!" in cond:
            inner = cond.get("!")
            if isinstance(inner, list):
                return not all(_api_eval_condition(node_data, c) for c in inner)
            return not _api_eval_condition(node_data, inner)
        if "key" in cond and "exp" in cond:
            return _api_eval_leaf(node_data, cond)

    return False

@app.route('/api/config/<config_uid>/node/<class_name>/query', methods=['POST'])
@api_auth_required
def nodes_api_query(config_uid, class_name):
    import nodes as _nodes_mod

    config = db.session.execute(
        select(Configuration).where(Configuration.uid == config_uid)
    ).scalar_one_or_none()
    if not config:
        abort(404)

    runtime_parsed = _build_runtime_parsed_config(config)
    ctx_tokens = _nodes_mod.set_runtime_context(config_uid, runtime_parsed)

    @after_this_request
    def _reset_ctx(resp):
        _nodes_mod.reset_runtime_context(ctx_tokens)
        return resp

    if not (os.path.isfile(_handlers_file_path(config_uid)) or config.nodes_server_handlers):
        abort(404)

    isolated_globals = _load_server_handlers_ns(config_uid, config)

    if (
        class_name not in isolated_globals or
        not hasattr(isolated_globals[class_name], '__bases__') or
        not any(base.__name__ == 'Node'
                for base in isolated_globals[class_name].__bases__)
    ):
        abort(404)

    node_class = isolated_globals[class_name]

    try:
        payload = request.get_json(silent=True)
        nodes = node_class.get_all(config_uid)

        # ["uid1","uid2",...]
        if isinstance(payload, list):
            wanted = set(str(x) for x in payload if x is not None)
            out = {}
            for node_id, node in nodes.items():
                d = node.to_dict()
                public_id = d.get("_data", {}).get("_id") or node_id
                if str(node_id) in wanted or str(public_id) in wanted:
                    out[node_id] = d
            return jsonify(out)

        # condition object
        if isinstance(payload, dict):
            out = {}
            for node_id, node in nodes.items():
                d = node.to_dict()
                data = d.get("_data", {}) or {}
                if _api_eval_condition(data, payload):
                    out[node_id] = d
            return jsonify(out)

        return jsonify({"error": "Body must be array of ids or condition object"}), 400

    except _nodes_mod.AcceptRejected as e:
        return jsonify({"status": False, "data": e.payload}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/catalog', methods=['GET'])
@api_auth_required
def api_catalog():
    user = getattr(g, "api_user", None)
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    owned = db.session.execute(
        select(Configuration).where(Configuration.user_id == user.id)
    ).scalars().all()

    shared = db.session.execute(
        select(Configuration)
        .join(UserConfigAccess, UserConfigAccess.config_id == Configuration.id)
        .where(UserConfigAccess.user_id == user.id)
    ).scalars().all()

    configs = {c.id: c for c in owned + shared}

    result = []
    for cfg in configs.values():
        cfg_uid = cfg.uid

        base_url = url_for('get_config', uid=cfg_uid, _external=True).replace('/api/config/', '/api/config/')


        classes = []
        for c in (cfg.classes or []):
            name = c.name
            classes.append({
                "name": name,
                "display_name": c.display_name or name,
                "urls": {
                    "get": f"{base_url}/node/{name}",
                    "post": f"{base_url}/node/{name}",
                    "query": f"{base_url}/node/{name}/query",
                }
            })

        datasets = []
        for d in (cfg.datasets or []):
            datasets.append({
                "name": d.name,
                "url": f"{base_url}/dataset/{d.name}/items"
            })

        result.append({
            "name": cfg.name,
            "uid": cfg_uid,
            "classes": classes,
            "datasets": datasets
        })

    return jsonify(result)


@app.route('/import-config-new', methods=['POST'])
@login_required
def import_config_new():
    """Import configuration from file - creates a new one or updates an existing one"""
    if 'config_file' not in request.files:
        flash(_('File not selected'), 'error')
        return redirect(url_for('dashboard'))
    
    file = request.files['config_file']
    if file.filename == '':
        flash(_('File not selected'), 'error')
        return redirect(url_for('dashboard'))
    
    if not file.filename.endswith('.nod'):
        flash(_('Only NOD files allowed'), 'error')
        return redirect(url_for('dashboard'))
    
    try:
        data = json.load(file.stream)
        
        print(f"Starting import of configuration")
        print(f"Data keys: {list(data.keys())}")
        
        
        imported_uid = data.get('uid')
        content_uid = data.get("content_uid")
        if not imported_uid:
            flash(_('Invalid configuration file: missing UID'), 'error')
            return redirect(url_for('dashboard'))
        
        # CHECKING IF A CONFIGURATION WITH THIS UID ALREADY EXISTS
        existing_config = db.session.execute(
            select(Configuration).where(Configuration.user_id==current_user.id, Configuration.content_uid==content_uid)
        ).scalar_one_or_none()
        
        if existing_config:
            # IF THE CONFIGURATION EXISTS, UPDATE IT
            print(f"Updating existing configuration: {existing_config.name}")
            
            # Checking access rights
            if existing_config.user_id != current_user.id:
                flash(_('You do not have permission to update this configuration'), 'error')
                return redirect(url_for('dashboard'))
            
            # UPDATE MAIN CONFIGURATION DATA
            existing_config.name = data.get('name', existing_config.name)
            existing_config.server_name = data.get('server_name', existing_config.server_name)
            existing_config.version = data.get('version', existing_config.version)
            existing_config.nodes_handlers = data.get('nodes_handlers', existing_config.nodes_handlers)
            existing_config.nodes_handlers_meta = data.get('nodes_handlers_meta', existing_config.nodes_handlers_meta)
            existing_config.nodes_server_handlers = data.get('nodes_server_handlers', existing_config.nodes_server_handlers)
            existing_config.nodes_server_handlers_meta = data.get('nodes_server_handlers_meta', existing_config.nodes_server_handlers_meta)
            
            # Delete all existing related data for a complete update
            print("Deleting existing related data...")
            for class_obj in existing_config.classes:
                db.session.delete(class_obj)
            for dataset in existing_config.datasets:
                db.session.delete(dataset)
            for section in existing_config.sections:
                db.session.delete(section)
            for server in existing_config.servers:
                db.session.delete(server)
            for event in existing_config.config_events:
                db.session.delete(event)    
            
            config_to_use = existing_config
            is_update = True
            
        else:
            # IF THERE IS NO CONFIGURATION - CREATE A NEW ONE
            print(f"Creating new configuration with UID: {imported_uid}")
            
            new_config = Configuration(
                name=data.get('name', _('Imported configuration')),
                server_name=data.get('server_name', ''),
                version=data.get('version', '00.00.01'),
                nodes_handlers=data.get('nodes_handlers', ''),
                nodes_handlers_meta=data.get('nodes_handlers_meta', {}),
                nodes_server_handlers=data.get('nodes_server_handlers', ''),
                nodes_server_handlers_meta=data.get('nodes_server_handlers_meta', {}),
                user_id=current_user.id,
                uid=str(uuid.uuid4()), 
                content_uid=content_uid,
                vendor=data.get("vendor")
            )
            
            db.session.add(new_config)
            db.session.flush()
            config_to_use = new_config
            is_update = False
        
        # IMPORT CLASSES (same for creation and update)
        classes_data = data.get('classes', [])
        print(f"Importing {len(classes_data)} classes...")
        
        for class_data in classes_data:
            new_class = ConfigClass(
                name=class_data['name'],
                section=class_data.get('section', ''),
                section_code=class_data.get('section_code', ''),
                has_storage=class_data.get('has_storage', False),
                display_name=class_data.get('display_name', class_data['name']),
                cover_image=class_data.get('cover_image', ''),
                class_type=class_data.get('class_type', ''),
                hidden=class_data.get('hidden', False),
                config_id=config_to_use.id
            )
            db.session.add(new_class)
            db.session.flush()
            
            # Import class methods
            methods_data = class_data.get('methods', [])
            print(f"  Importing {len(methods_data)} methods for class {class_data['name']}")
            
            for method_data in methods_data:
                new_method = ClassMethod(
                    name=method_data['name'],
                    source=method_data.get('source', 'internal'),
                    engine=method_data['engine'],
                    code=method_data['code'],
                    class_id=new_class.id
                )
                db.session.add(new_method)
            
            # Import class events
            events_data = class_data.get('events', [])
            print(f"  Importing {len(events_data)} events for class {class_data['name']}")
            
            for event_data in events_data:
                new_event = ClassEvent(
                    event=event_data['event'],
                    listener=event_data.get('listener', ''),
                    class_id=new_class.id
                )
                db.session.add(new_event)
                db.session.flush()
                
                # Import event actions
                actions_data = event_data.get('actions', [])
                print(f"    Importing {len(actions_data)} actions for event {event_data['event']}")
                
                for action_data in actions_data:
                    new_action = EventAction(
                        action=action_data.get('action', 'run'),
                        source=action_data.get('source', 'internal'),
                        server=action_data.get('server', ''),
                        method=action_data.get('method', ''),
                        post_execute_method=action_data.get('postExecuteMethod', ''),
                        order=action_data.get('order', 0),
                        event_id=new_event.id
                    )
                    db.session.add(new_action)
        
        # Import datasets
        datasets_data = data.get('datasets', [])
        print(f"Importing {len(datasets_data)} datasets...")
        
        for dataset_data in datasets_data:
            # Convert arrays back to strings for storage in the database
            hash_indexes = ','.join(dataset_data.get('hash_indexes', [])) if isinstance(dataset_data.get('hash_indexes'), list) else dataset_data.get('hash_indexes', '')
            text_indexes = ','.join(dataset_data.get('text_indexes', [])) if isinstance(dataset_data.get('text_indexes'), list) else dataset_data.get('text_indexes', '')
            
            new_dataset = Dataset(
                name=dataset_data['name'],
                hash_indexes=hash_indexes,
                text_indexes=text_indexes,
                view_template=dataset_data.get('view_template', ''),
                autoload=dataset_data.get('autoload', False),
                config_id=config_to_use.id
            )
            db.session.add(new_dataset)
        
        # Import sections
        sections_data = data.get('sections', [])
        print(f"Importing {len(sections_data)} sections...")
        
        for section_data in sections_data:
            new_section = ConfigSection(
                name=section_data['name'],
                code=section_data['code'],
                commands=section_data.get('commands', ''),
                config_id=config_to_use.id
            )
            db.session.add(new_section)
        
        # Import servers
        servers_data = data.get('servers', [])
        print(f"Importing {len(servers_data)} servers...")
        
        for server_data in servers_data:
            new_server = Server(
                alias=server_data['alias'],
                url=server_data['url'],
                is_default=server_data.get('is_default', False),
                config_id=config_to_use.id
            )
            db.session.add(new_server)

        common_events_data = data.get('CommonEvents', [])
        print(f"Importing {len(common_events_data)} common events.")

        for ev_data in common_events_data:
            new_event = ConfigEvent(
                event=ev_data['event'],
                listener=ev_data.get('listener', ''),
                config_id=config_to_use.id
            )
            db.session.add(new_event)

            for action_data in ev_data.get('actions', []):
                new_action = ConfigEventAction(
                    event_obj=new_event,
                    action=action_data.get('action', ''),
                    source=action_data.get('source', ''),
                    server=action_data.get('server', ''),
                    method=action_data.get('method', ''),
                    post_execute_method=action_data.get('postExecuteMethod', '')
                )
                db.session.add(new_action)    
        
        # CREATE/UPDATE THE SERVER HANDLERS FILE IF THERE ARE ANY
        if config_to_use.nodes_server_handlers:
            handlers_dir = os.path.join('Handlers', config_to_use.uid)
            os.makedirs(handlers_dir, exist_ok=True)
            handlers_file_path = os.path.join(handlers_dir, 'handlers.py')
            try:
                handlers_code = base64.b64decode(config_to_use.nodes_server_handlers).decode('utf-8')
                with open(handlers_file_path, 'w', encoding='utf-8') as f:
                    f.write(handlers_code)
                print(f"Created/updated server handlers file: {handlers_file_path}")
            except Exception as e:
                print(f"Error creating server handlers file: {str(e)}")
        
        # Updating the timestamp
        config_to_use.update_last_modified()
        
        db.session.commit()
        
        if is_update:
            print(f"Configuration updated successfully: {config_to_use.name}")
            flash(_('Configuration updated successfully'), 'success')
        else:
            print(f"Configuration imported successfully: {config_to_use.name}")
            flash(_('Configuration imported successfully'), 'success')
        
        return redirect(url_for('edit_config', uid=config_to_use.uid))
        
    except Exception as e:
        db.session.rollback()
        error_msg = f'Import error: {str(e)}'
        print(error_msg)
        traceback.print_exc()
        flash(_('Import error: {error}').format(error=str(e)), 'error')
        return redirect(url_for('dashboard'))


def apply_full_config_from_json(config, data):
    """
    Completely updates the config configuration using JSON data.
    1-to-1 logic with the current import_config.
    """
    # COMPLETE UPDATE OF ALL CONFIGURATION FIELDS
    config.name = data.get('name', config.name)
    config.vendor = data.get('vendor', config.vendor)
    config.server_name = data.get('server_name', config.server_name)
    config.version = data.get('version', config.version)
    config.nodes_handlers = data.get('nodes_handlers', config.nodes_handlers)
    config.nodes_handlers_meta = data.get('nodes_handlers_meta', config.nodes_handlers_meta)
    config.nodes_server_handlers = data.get('nodes_server_handlers', config.nodes_server_handlers)
    config.nodes_server_handlers_meta = data.get('nodes_server_handlers_meta', config.nodes_server_handlers_meta)
    
    # We delete ALL existing related data
    print("Deleting existing data...")
    for class_obj in config.classes:
        db.session.delete(class_obj)
    for dataset in config.datasets:
        db.session.delete(dataset)
    for section in config.sections:
        db.session.delete(section)
    for server in config.servers:
        db.session.delete(server)
    for event in config.config_events:
        db.session.delete(event)    
    
    # Importing classes
    classes_data = data.get('classes', [])
    print(f"Importing {len(classes_data)} classes...")
    
    for class_data in classes_data:
        new_class = ConfigClass(
            name=class_data['name'],
            section=class_data.get('section', ''),
            section_code=class_data.get('section_code', ''),
            has_storage=class_data.get('has_storage', False),
            display_name=class_data.get('display_name', class_data['name']),
            cover_image=class_data.get('cover_image', ''),
            class_type=class_data.get('class_type', ''),
            hidden=class_data.get('hidden', False),
            config_id=config.id
        )
        db.session.add(new_class)
        db.session.flush()
        
        # Importing class methods
        methods_data = class_data.get('methods', [])
        print(f"  Importing {len(methods_data)} methods for class {class_data['name']}")
        
        for method_data in methods_data:
            new_method = ClassMethod(
                name=method_data['name'],
                source=method_data.get('source', 'internal'),
                engine=method_data['engine'],
                code=method_data['code'],
                class_id=new_class.id
            )
            db.session.add(new_method)
        
        # Importing class events
        events_data = class_data.get('events', [])
        print(f"  Importing {len(events_data)} events for class {class_data['name']}")
        
        for event_data in events_data:
            new_event = ClassEvent(
                event=event_data['event'],
                listener=event_data.get('listener', ''),
                class_id=new_class.id
            )
            db.session.add(new_event)
            db.session.flush()
            
            # Importing event actions
            actions_data = event_data.get('actions', [])
            print(f"    Importing {len(actions_data)} actions for event {event_data['event']}")
            
            for action_data in actions_data:
                new_action = EventAction(
                    action=action_data.get('action', 'run'),
                    source=action_data.get('source', 'internal'),
                    server=action_data.get('server', ''),
                    method=action_data.get('method', ''),
                    post_execute_method=action_data.get('postExecuteMethod', ''),
                    order=action_data.get('order', 0),
                    event_id=new_event.id
                )
                db.session.add(new_action)
    
    # Importing datasets
    datasets_data = data.get('datasets', [])
    print(f"Importing {len(datasets_data)} datasets...")
    
    for dataset_data in datasets_data:
        # Converting arrays back to strings for storage in the database
        hash_indexes = ','.join(dataset_data.get('hash_indexes', [])) \
            if isinstance(dataset_data.get('hash_indexes'), list) \
            else dataset_data.get('hash_indexes', '')
        text_indexes = ','.join(dataset_data.get('text_indexes', [])) \
            if isinstance(dataset_data.get('text_indexes'), list) \
            else dataset_data.get('text_indexes', '')
        
        new_dataset = Dataset(
            name=dataset_data['name'],
            hash_indexes=hash_indexes,
            text_indexes=text_indexes,
            view_template=dataset_data.get('view_template', ''),
            autoload=dataset_data.get('autoload', False),
            config_id=config.id
        )
        db.session.add(new_dataset)
    
    # Importing sections
    sections_data = data.get('sections', [])
    print(f"Importing {len(sections_data)} sections...")
    
    for section_data in sections_data:
        new_section = ConfigSection(
            name=section_data['name'],
            code=section_data['code'],
            commands=section_data.get('commands', ''),
            config_id=config.id
        )
        db.session.add(new_section)
    
    # Importing servers
    servers_data = data.get('servers', [])
    print(f"Importing {len(servers_data)} servers...")
    
    for server_data in servers_data:
        new_server = Server(
            alias=server_data['alias'],
            url=server_data['url'],
            is_default=server_data.get('is_default', False),
            config_id=config.id
        )
        db.session.add(new_server)

     # Importing common events
    common_events_data = data.get('CommonEvents', [])
    print(f"Importing {len(common_events_data)} common events.")

    for ev_data in common_events_data:
        new_event = ConfigEvent(
            event=ev_data['event'],
            listener=ev_data.get('listener', ''),
            config_id=config.id
        )
        db.session.add(new_event)

        for action_data in ev_data.get('actions', []):
            new_action = ConfigEventAction(
                event_obj=new_event,
                action=action_data.get('action', ''),
                source=action_data.get('source', ''),
                server=action_data.get('server', ''),
                method=action_data.get('method', ''),
                post_execute_method=action_data.get('postExecuteMethod', '')
            )
            db.session.add(new_action)    
    
    # Updating the timestamp
    config.update_last_modified()
    
    # CREATE/UPDATE THE SERVER HANDLERS FILE IF THERE ARE ANY
    if config.nodes_server_handlers:
        handlers_dir = os.path.join('Handlers', config.uid)
        os.makedirs(handlers_dir, exist_ok=True)
        handlers_file_path = os.path.join(handlers_dir, 'handlers.py')
        try:
            handlers_code = base64.b64decode(config.nodes_server_handlers).decode('utf-8')
            with open(handlers_file_path, 'w', encoding='utf-8') as f:
                f.write(handlers_code)
            print(f"Created/updated server handlers file: {handlers_file_path}")
        except Exception as e:
            print(f"Error creating server handlers file: {str(e)}")


@app.route('/import-config/<uid>', methods=['POST'])
@login_required
def import_config(uid):
    config = db.session.execute(
        select(Configuration).where(Configuration.uid == uid, Configuration.user_id == current_user.id)
    ).scalar_one_or_none()
    
    if not config:
        abort(404)
    
    if 'config_file' not in request.files:
        flash(_('File not selected'), 'error')
        return redirect(url_for('edit_config', uid=uid))
    
    file = request.files['config_file']
    if file.filename == '':
        flash(_('File not selected'), 'error')
        return redirect(url_for('edit_config', uid=uid))
    
    if not file.filename.endswith('.json'):
        flash(_('Only JSON files allowed'), 'error')
        return redirect(url_for('edit_config', uid=uid))
    
    try:
        data = json.load(file.stream)
        
        print(f"Starting import for config {uid}")
        print(f"Data keys: {list(data.keys())}")
        
        
        apply_full_config_from_json(config, data)
        
        db.session.commit()
        print("Import completed successfully")
        
        flash(_('Configuration imported successfully'), 'success')
        
    except Exception as e:
        db.session.rollback()
        error_msg = f'Import error: {str(e)}'
        print(error_msg)
        traceback.print_exc()
        flash(_('Import error: {error}').format(error=str(e)), 'error')
    
    active_tab = request.form.get("active_tab", "config")
    return redirect(url_for('edit_config', uid=uid, tab=active_tab))


def call_deepseek(system_prompt: str, user_prompt: str) -> str:
    if not DEEPSEEK_API_KEY:
        raise RuntimeError("DEEPSEEK_API_KEY is not set")

    headers = {
        'Authorization': f'Bearer {DEEPSEEK_API_KEY}',
        'Content-Type': 'application/json'
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 8000
    }
    resp = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]

def call_lmstudio(system_prompt: str, user_prompt: str) -> str:
    # LM Studio обычно OpenAI-compatible: /v1/chat/completions
    headers = {"Content-Type": "application/json"}
    if LMSTUDIO_API_KEY:
        headers["Authorization"] = f"Bearer {LMSTUDIO_API_KEY}"

    payload = {
        "model": LMSTUDIO_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
    }

    resp = requests.post(LMSTUDIO_API_URL, headers=headers, json=payload, timeout=1200)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def call_llm(provider: str, system_prompt: str, user_prompt: str) -> str:
    provider = (provider or "").strip().lower()
    if provider == "lmstudio":
        return call_lmstudio(system_prompt, user_prompt)
    # default
    return call_deepseek(system_prompt, user_prompt)


def extract_json_array_from_text(text: str) -> str:
    """Extract the largest JSON array substring from an LLM response."""
    if not text:
        raise ValueError("Empty LLM response")

    s = text.strip()

    # Strip markdown fences if present
    if s.startswith("```"):
        first_nl = s.find("\n")
        if first_nl != -1:
            s = s[first_nl + 1:]
        end_fence = s.rfind("```")
        if end_fence != -1:
            s = s[:end_fence].strip()

    start = s.find("[")
    end = s.rfind("]")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON array found in LLM response")

    candidate = s[start:end + 1].strip()
    json.loads(candidate)  # validation
    return candidate


def extract_json_from_text(text: str) -> str:
    if not text:
        raise ValueError("Empty LLM response")

    s = text.strip()

    # Strip markdown fences if present
    if s.startswith("```"):
        # remove first fence line
        first_nl = s.find("\n")
        if first_nl != -1:
            s = s[first_nl+1:]
        # remove last fence
        end_fence = s.rfind("```")
        if end_fence != -1:
            s = s[:end_fence].strip()

    # Now take the largest JSON object substring
    start = s.find("{")
    end = s.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in LLM response")

    candidate = s[start:end+1].strip()

    # Quick validation pass (raises with location)
    json.loads(candidate)
    return candidate




ALLOWED_UI_TYPES_AI = {
    # BASIC
    "Text", "Picture", "HTML", "Button", "BottomButtons", "Input", "Switch", "CheckBox",
    "Table", "Parameters", "NodeChildren", "DatasetField",

    # CONTAINERS
    "VerticalLayout", "HorizontalLayout", "VerticalScroll", "HorizontalScroll", "Card",

    # PLUGINS (PlugIn)
    "FloatingButton", "ToolbarButton",
    "PhotoButton", "GalleryButton", "MediaGallery",
    "CameraBarcodeScannerButton",  # camera scan button
    "BarcodeScanner",              # hardware scanner interception (TSD terminals)
}

CONTAINER_UI_TYPES_AI = {"VerticalLayout", "HorizontalLayout", "VerticalScroll", "HorizontalScroll", "Card"}

ALLOWED_INPUT_TYPES_AI = {"NUMBER", "PASSWORD", "MULTILINE", "DATE"}

def _split_commands_str(commands: str):
    # "Caption|code,Caption2|code2" -> [("Caption","code"), ...]
    items = []
    if commands is None:
        return items, ["commands is null (must be string)"]
    if not isinstance(commands, str):
        return items, [f"commands must be string (got {type(commands).__name__})"]
    s = commands.strip()
    if s == "":
        return [], []
    parts = [p.strip() for p in s.split(",") if p.strip()]
    errors = []
    for p in parts:
        if "|" not in p:
            errors.append(f"bad command '{p}' (missing '|')")
            continue
        title, code = p.split("|", 1)
        title = title.strip()
        code = code.strip()
        if not title or not code:
            errors.append(f"bad command '{p}' (empty title or code)")
            continue
        items.append((title, code))
    return items, errors

def validate_sections_ai(cfg: dict):
    errors = []
    sections = cfg.get("sections", [])
    if sections is None:
        return ["sections is null (must be list)"]
    if not isinstance(sections, list):
        return [f"sections must be list (got {type(sections).__name__})"]
    for i, sec in enumerate(sections):
        if not isinstance(sec, dict):
            errors.append(f"sections[{i}] must be object")
            continue
        name = sec.get("name")
        code = sec.get("code")
        commands = sec.get("commands", "")
        if not isinstance(name, str) or not name.strip():
            errors.append(f"sections[{i}].name must be non-empty string")
        if not isinstance(code, str) or not code.strip():
            errors.append(f"sections[{i}].code must be non-empty string")
        # forbidden UI-like fields (common hallucination)
        for forbidden in ("layout", "type", "value", "items"):
            if forbidden in sec:
                errors.append(f"sections[{i}] must NOT contain '{forbidden}' (sections are navigation, not UI)")
        _, cmd_err = _split_commands_str(commands)
        for e in cmd_err:
            errors.append(f"sections[{i}].commands: {e}")
    return errors

def _iter_layout_elements_ai(layout):
    # layout root is list of rows; each row list of dicts; may include container dicts with nested "value"/"layout"
    if isinstance(layout, list):
        for item in layout:
            if isinstance(item, dict):
                yield item
                t = item.get("type")
                if t in CONTAINER_UI_TYPES_AI and isinstance(item.get("value"), list):
                    yield from _iter_layout_elements_ai(item["value"])
                if t == "BottomButtons" and isinstance(item.get("value"), list):
                    yield from _iter_layout_elements_ai(item["value"])
                if t == "Table" and isinstance(item.get("layout"), list):
                    yield from _iter_layout_elements_ai(item["layout"])
            else:
                yield from _iter_layout_elements_ai(item)

def validate_layout_types_ai(layout, where="layout"):
    errors = []
    for el in _iter_layout_elements_ai(layout):
        if not isinstance(el, dict):
            continue
        t = el.get("type")
        if not isinstance(t, str) or not t:
            errors.append(f"{where}: element without valid 'type'")
            continue
        if t not in ALLOWED_UI_TYPES_AI:
            errors.append(f"{where}: unknown UI type '{t}' (type is CASE-SENSITIVE)")
        # Text.size must be int
        if t == "Text" and "size" in el and not isinstance(el.get("size"), int):
            errors.append(f"{where}: Text.size must be integer (got {type(el.get('size')).__name__})")
        # Input.input_type must be one of allowed (if present)
        if t == "Input" and "input_type" in el:
            it = el.get("input_type")
            if not isinstance(it, str) or it not in ALLOWED_INPUT_TYPES_AI:
                errors.append(f"{where}: Input.input_type must be one of {sorted(ALLOWED_INPUT_TYPES_AI)} (got {it!r})")
    return errors

def validate_cover_images_ai(cfg: dict):
    errors = []
    classes = cfg.get("classes", []) or []
    if not isinstance(classes, list):
        return [f"classes must be list (got {type(classes).__name__})"]
    for i, cls in enumerate(classes):
        if not isinstance(cls, dict):
            errors.append(f"classes[{i}] must be object")
            continue
        ci = cls.get("cover_image")
        if not isinstance(ci, str) or not ci.strip():
            errors.append(f"classes[{i}].cover_image must be non-empty string (JSON-in-string layout)")
            continue
        try:
            layout = json.loads(ci)
        except Exception as e:
            errors.append(f"classes[{i}].cover_image must be valid JSON string layout: {e}")
            continue
        if not isinstance(layout, list):
            errors.append(f"classes[{i}].cover_image root must be a list")
            continue
        errors.extend(validate_layout_types_ai(layout, where=f"classes[{i}].cover_image"))
    return errors

def split_handlers_by_immutable_prefix_ai(current_code: str, llm_code: str):
    """
    Preserve everything ABOVE and INCLUDING the line 'from nodes import Node' from current_code.
    Replace everything below that line by llm_code's below-marker part.
    """
    marker = "from nodes import Node"
    cur_idx = current_code.find(marker)
    llm_idx = llm_code.find(marker)
    if cur_idx == -1 or llm_idx == -1:
        # if marker not found, safest is to use llm_code as is (or keep current). Here: use llm_code.
        return llm_code

    cur_line_end = current_code.find("\n", cur_idx)
    llm_line_end = llm_code.find("\n", llm_idx)
    if cur_line_end == -1 or llm_line_end == -1:
        return llm_code

    immutable_prefix = current_code[:cur_line_end + 1]
    mutable_suffix = llm_code[llm_line_end + 1:]
    return immutable_prefix + mutable_suffix

def _decode_b64_py(b64: str):
    if not b64:
        return ""
    return base64.b64decode(b64).decode("utf-8", errors="replace")

def _encode_b64_py(code: str):
    return base64.b64encode(code.encode("utf-8")).decode("utf-8")

def validate_handlers_semantics_ai(py_code: str, where="handlers"):
    """Validate: methods have input_data=None and return (bool, dict)."""
    errors = []
    try:
        tree = ast.parse(py_code)
    except SyntaxError as e:
        return [f"{where}: syntax error: {e}"]

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # ignore dunder and __init__
            if node.name.startswith("__") or node.name == "__init__":
                continue

            # must accept input_data
            args = node.args.args or []
            has_input = any(a.arg == "input_data" for a in args)
            if not has_input:
                errors.append(f"{where}: {node.name} must accept parameter input_data=None")
            else:
                # check default None
                total = len(args)
                ndef = len(node.args.defaults or [])
                default_map = {}
                for a, d in zip(args[total-ndef:], node.args.defaults):
                    default_map[a.arg] = d
                d = default_map.get("input_data")
                if d is None or not isinstance(d, ast.Constant) or d.value is not None:
                    errors.append(f"{where}: {node.name} input_data must default to None")

            # must return tuple of 2 elements somewhere
            returns = [n for n in ast.walk(node) if isinstance(n, ast.Return)]
            if not returns:
                errors.append(f"{where}: {node.name} must return (bool, dict)")
            else:
                ok_any = any(isinstance(r.value, ast.Tuple) and len(r.value.elts) == 2 for r in returns)
                if not ok_any:
                    errors.append(f"{where}: {node.name} must return a tuple of 2 elements (bool, dict)")
    return errors

class _ShowPlugInLiteralValidatorAI(ast.NodeVisitor):
    """Validate only static literals for Show([...]) and PlugIn([...]) calls."""
    def __init__(self):
        self.errors = []

    def visit_Call(self, node: ast.Call):
        func = node.func
        name = None
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id == "self":
            name = func.attr

        if name in ("Show", "PlugIn") and node.args:
            arg0 = node.args[0]
            if name == "PlugIn":
                # PlugIn must be 1D list of dicts
                if isinstance(arg0, ast.List):
                    for el in arg0.elts:
                        if not isinstance(el, ast.Dict):
                            self.errors.append("PlugIn(...): must be list of objects (dict)")
                        else:
                            self._validate_element_dict(el, where="PlugIn(... )")
                else:
                    # don't hard-fail non-literal; skip
                    pass
            else:
                # Show must be layout (2D list)
                self._validate_layout_literal(arg0, where="Show(... )")

        self.generic_visit(node)

    def _validate_layout_literal(self, n, where):
        if isinstance(n, ast.List):
            for el in n.elts:
                self._validate_layout_literal(el, where)
        elif isinstance(n, ast.Dict):
            self._validate_element_dict(n, where)

    def _validate_element_dict(self, dnode: ast.Dict, where):
        keys = []
        for k in dnode.keys:
            if isinstance(k, ast.Constant) and isinstance(k.value, str):
                keys.append(k.value)
            else:
                keys.append(None)
        d = dict(zip(keys, dnode.values))

        tnode = d.get("type")
        if isinstance(tnode, ast.Constant) and isinstance(tnode.value, str):
            t = tnode.value
            if t not in ALLOWED_UI_TYPES_AI:
                self.errors.append(f"{where}: unknown UI type '{t}' (CASE-SENSITIVE)")
            if t == "Text":
                snode = d.get("size")
                if snode is not None and not (isinstance(snode, ast.Constant) and isinstance(snode.value, int)):
                    self.errors.append(f"{where}: Text.size must be integer literal")
            if t == "Input":
                inode = d.get("input_type")
                if inode is not None and not (isinstance(inode, ast.Constant) and isinstance(inode.value, str) and inode.value in ALLOWED_INPUT_TYPES_AI):
                    self.errors.append(f"{where}: Input.input_type must be one of {sorted(ALLOWED_INPUT_TYPES_AI)} (CASE-SENSITIVE)")

            # recurse for containers / bottom buttons / table
            if t in CONTAINER_UI_TYPES_AI:
                self._validate_layout_literal(d.get("value"), where)
            if t == "BottomButtons":
                self._validate_layout_literal(d.get("value"), where)
            if t == "Table":
                self._validate_layout_literal(d.get("layout"), where)

def validate_show_plugin_literals_ai(py_code: str):
    try:
        tree = ast.parse(py_code)
    except SyntaxError:
        return []
    v = _ShowPlugInLiteralValidatorAI()
    v.visit(tree)
    return v.errors

def extract_method_names_ai(py_code: str):
    """Collect method names from all non-Node classes (android handlers)."""
    names = set()
    try:
        tree = ast.parse(py_code)
    except Exception:
        return names
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            if node.name == "Node":
                continue
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    if item.name.startswith("__") or item.name == "__init__":
                        continue
                    names.add(item.name)
    return names

def validate_sections_command_targets_ai(cfg: dict, android_method_names: set):
    """Optional cross-check: each command_code must exist in android handlers methods."""
    errors = []
    for i, sec in enumerate(cfg.get("sections", []) or []):
        if not isinstance(sec, dict):
            continue
        commands = sec.get("commands", "")
        items, cmd_errs = _split_commands_str(commands)
        # syntax errors already reported in validate_sections_ai; skip those here
        if cmd_errs:
            continue
        for _title, code in items:
            if code not in android_method_names:
                errors.append(f"sections[{i}].commands references missing android handler method '{code}'")
    return errors

def _deep_merge_dict_keep_existing(dst: dict, src: dict) -> dict:
    """
    Merge src into dst recursively:
    - if src has key -> it overwrites/merges
    - if src missing key -> keep dst
    Lists are replaced as a whole unless handled specially elsewhere.
    """
    out = dict(dst)
    for k, v in (src or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge_dict_keep_existing(out[k], v)
        else:
            out[k] = v
    return out

def _upsert_list_by_key_keep_missing(current_list, patch_list, key_fn, merge_item_fn=None):
    """
    Upsert items from patch_list into current_list by identity key_fn(item).
    Items not present in patch_list remain unchanged.
    """
    if current_list is None:
        current_list = []
    if patch_list is None:
        return list(current_list)

    if not isinstance(current_list, list):
        current_list = []
    if not isinstance(patch_list, list):
        return list(current_list)

    out = list(current_list)
    index = {}
    for i, it in enumerate(out):
        if isinstance(it, dict):
            try:
                index[key_fn(it)] = i
            except Exception:
                pass

    for pit in patch_list:
        if not isinstance(pit, dict):
            continue
        try:
            k = key_fn(pit)
        except Exception:
            continue
        if k in index:
            i = index[k]
            if merge_item_fn:
                out[i] = merge_item_fn(out[i], pit)
            else:
                out[i] = _deep_merge_dict_keep_existing(out[i], pit)
        else:
            out.append(pit)
            index[k] = len(out) - 1
    return out

def _merge_class(old_cls: dict, new_cls: dict) -> dict:
    out = _deep_merge_dict_keep_existing(old_cls, new_cls)

    # methods: upsert by name
    out["methods"] = _upsert_list_by_key_keep_missing(
        old_cls.get("methods", []) if isinstance(old_cls, dict) else [],
        new_cls.get("methods", []) if isinstance(new_cls, dict) else [],
        key_fn=lambda m: m.get("name"),
        merge_item_fn=_deep_merge_dict_keep_existing,
    )

    # events: upsert by (event, listener)
    out["events"] = _upsert_list_by_key_keep_missing(
        old_cls.get("events", []) if isinstance(old_cls, dict) else [],
        new_cls.get("events", []) if isinstance(new_cls, dict) else [],
        key_fn=lambda e: (e.get("event"), e.get("listener", "")),
        merge_item_fn=_deep_merge_dict_keep_existing,
    )
    return out

def merge_llm_config_into_current_ai(current_cfg: dict, llm_cfg: dict):
    """
    PATCH semantics (safe):
    - Upsert classes/datasets/sections/CommonEvents by identity keys.
    - Do NOT delete anything unless TT explicitly requests (we don't support delete via AI by default).
    - Merge handlers preserving immutable prefix.
    - Keep all unrelated root fields from current_cfg.
    """
    out = dict(current_cfg)

    # classes upsert by name
    if "classes" in llm_cfg:
        out["classes"] = _upsert_list_by_key_keep_missing(
            current_cfg.get("classes", []),
            llm_cfg.get("classes", []),
            key_fn=lambda c: c.get("name"),
            merge_item_fn=_merge_class,
        )

    # datasets upsert by name
    if "datasets" in llm_cfg:
        out["datasets"] = _upsert_list_by_key_keep_missing(
            current_cfg.get("datasets", []),
            llm_cfg.get("datasets", []),
            key_fn=lambda d: d.get("name"),
            merge_item_fn=_deep_merge_dict_keep_existing,
        )

    # sections upsert by code (fallback to name if code missing)
    if "sections" in llm_cfg:
        out["sections"] = _upsert_list_by_key_keep_missing(
            current_cfg.get("sections", []),
            llm_cfg.get("sections", []),
            key_fn=lambda s: s.get("code") or s.get("name"),
            merge_item_fn=_deep_merge_dict_keep_existing,
        )

    # CommonEvents upsert by (event, listener)
    if "CommonEvents" in llm_cfg:
        out["CommonEvents"] = _upsert_list_by_key_keep_missing(
            current_cfg.get("CommonEvents", []),
            llm_cfg.get("CommonEvents", []),
            key_fn=lambda e: (e.get("event"), e.get("listener", "")),
            merge_item_fn=_deep_merge_dict_keep_existing,
        )

    # Handlers: preserve current prefix up to+including "from nodes import Node"
    for field in ("nodes_handlers", "nodes_server_handlers"):
        cur_code = _decode_b64_py(current_cfg.get(field) or "")
        llm_code = _decode_b64_py(llm_cfg.get(field) or "")
        if llm_code.strip():
            merged = split_handlers_by_immutable_prefix_ai(cur_code, llm_code) if cur_code.strip() else llm_code
            out[field] = _encode_b64_py(merged)
        else:
            out[field] = current_cfg.get(field)

    return out


def validate_full_llm_config_ai(cfg: dict):
    """
    Full AI-only validation:
    - sections structure + commands format (+ cross-check to android handlers)
    - cover_image JSON-in-string layout + allowed UI types + Text.size + Input.input_type
    - handlers: python syntax + method signature + return tuple + Show/PlugIn literal checks
    """
    errors = []
    #errors.extend(validate_sections_ai(cfg))
    #errors.extend(validate_cover_images_ai(cfg))

    android_code = _decode_b64_py(cfg.get("nodes_handlers") or "")
    server_code = _decode_b64_py(cfg.get("nodes_server_handlers") or "")

    # handlers python parse
    for field, code in (("nodes_handlers", android_code), ("nodes_server_handlers", server_code)):
        if not code.strip():
            errors.append(f"{field}: empty")
            continue
        try:
            ast.parse(code)
        except SyntaxError as e:
            errors.append(f"{field}: syntax error: {e}")
            continue
        errors.extend(validate_handlers_semantics_ai(code, where=field))
        errors.extend(validate_show_plugin_literals_ai(code))

    # cross-check sections commands -> android methods
    #android_methods = extract_method_names_ai(android_code) if android_code.strip() else set()
    #errors.extend(validate_sections_command_targets_ai(cfg, android_methods))

    return errors

def _decode_b64_text(b64: str) -> str:
    if not b64:
        return ""
    try:
        return base64.b64decode(b64).decode("utf-8")
    except Exception:
       
        return ""

def _encode_b64_text(text: str) -> str:
    return base64.b64encode((text or "").encode("utf-8")).decode("utf-8")

def _split_handlers_header_and_body(code: str):
    """
    Header = everything before and including the line 'from nodes import Node'
    Body = everything after this line (usually class ...).
    If the marker is not found, the header is empty, and body = all code.
    """
    if not code:
        return "", ""
    marker = "from nodes import Node"
    idx = code.find(marker)
    if idx == -1:
        return "", code

    # we take the whole line with the marker
    line_end = code.find("\n", idx)
    if line_end == -1:
        
        return code + "\n", ""

    header = code[: line_end + 1]
    body = code[line_end + 1 :]

    # We don't touch the header, but the body can be slightly normalized by leading line breaks
    body = body.lstrip("\n")
    return header, body

def _call_llm_code_only(provider: str, system_prompt: str, user_prompt: str) -> str:
    """
    Calls LLM and returns the text "as is", but:
    - truncates the ``` if LLM did send it
    """
    txt = call_llm(provider, system_prompt, user_prompt) or ""
    s = txt.strip()
    if s.startswith("```"):
        # снять fence
        first_nl = s.find("\n")
        if first_nl != -1:
            s = s[first_nl + 1 :]
        end_fence = s.rfind("```")
        if end_fence != -1:
            s = s[:end_fence].strip()
    return s.strip()

def _generate_handlers_body_ai(
    provider: str,
    system_prompt: str,
    user_request: str,
    merged_config_json: dict,
    current_header: str,
    current_body: str,
    kind_label: str,   # "ANDROID" or "SERVER"
    max_attempts: int = 3,
):
    """
    Generates ONLY the body (after the header) for handlers.
    We keep the header exactly the same as in the current configuration.
    """
    # Strict requirements for the response format
    base_prompt = (
        f"You are updating NodaLogic {kind_label} handlers.\n"
        "Return ONLY python code BODY (no imports, no constants, no markdown, no ```).\n"
        "The BODY must start with class definitions (e.g., 'class ...').\n"
        "Do NOT repeat the header. Do NOT include 'from nodes import Node'.\n"
        "Keep method signatures and return types exactly as required by the NodaLogic LLM rules.\n"
        "Each method must have parameters and must return a tuple: (bool, dict).\n"
        "\n"
        "User request:\n"
        f"{user_request}\n\n"
        "Merged configuration JSON (without needing to include huge handler base64):\n"
        f"{json.dumps(merged_config_json, ensure_ascii=False, indent=2)}\n\n"
        "Current immutable header (DO NOT CHANGE IT):\n"
        f"{current_header}\n\n"
        "Current handlers BODY (edit this):\n"
        f"{current_body}\n"
    )

    body = None
    last_err = None

    for attempt in range(1, max_attempts + 1):
        prompt = base_prompt if attempt == 1 else (
            base_prompt
            + "\n\n"
            "The previous BODY is invalid.\n"
            f"Error:\n{last_err}\n\n"
            "Fix the BODY and return ONLY the corrected BODY.\n"
        )

        candidate_body = _call_llm_code_only(provider, system_prompt, prompt)

        # Quick check: Does it look like body (must start with class/decorator)
        if not candidate_body or ("from nodes import Node" in candidate_body) or ("import " in candidate_body[:200]):
            last_err = "LLM returned header/imports or empty text. Must return only class body."
            continue

        full_code = (current_header or "") + "\n" + candidate_body.strip() + "\n"
        ok, err = validate_python_syntax(full_code)  # Do not touch validate_python_syntax globally.
        if ok:
            return candidate_body.strip()

        last_err = err

    raise RuntimeError(f"Failed to generate valid {kind_label} handlers body after {max_attempts} attempts: {last_err}")

def ensure_handlers_skeleton_and_headers(config_uid: str, config_url: str, cfg: dict):
    """
    Ensures that:
    - nodes_handlers contains ANDROID_IMPORTS_TEMPLATE + from nodes import Node
    - nodes_server_handlers contains from nodes import Node
    Even if LLM did not return a server file.
    """
    # ANDROID
    android_code = _decode_b64_text(cfg.get("nodes_handlers", "") or "")
    if not android_code.strip():
        android_imports = ANDROID_IMPORTS_TEMPLATE.format(uid=config_uid, config_url=config_url)
        android_code = android_imports + NODE_CLASS_CODE_ANDROID.strip() + "\n"
        cfg["nodes_handlers"] = _encode_b64_text(android_code)
    else:
        # If someone brings an Android without Node, we'll add it (as in upload/create_class)
        if "from nodes import Node" not in android_code:
            android_imports = ANDROID_IMPORTS_TEMPLATE.format(uid=config_uid, config_url=config_url)
            android_code = android_imports + NODE_CLASS_CODE_ANDROID.strip() + "\n" + android_code
            cfg["nodes_handlers"] = _encode_b64_text(android_code)

    # SERVER
    server_code = _decode_b64_text(cfg.get("nodes_server_handlers", "") or "")
    if not server_code.strip():
        server_code = NODE_CLASS_CODE.strip() + "\n"
        cfg["nodes_server_handlers"] = _encode_b64_text(server_code)
    else:
        if "from nodes import Node" not in server_code:
            server_code = NODE_CLASS_CODE.strip() + "\n\n" + server_code
            cfg["nodes_server_handlers"] = _encode_b64_text(server_code)


def ensure_all_classes_present_in_handlers(cfg: dict):
    """
    For each class in the JSON, it guarantees that the class exists:
    - in android handlers
    - in server handlers

    IMPORTANT: We use the same init signatures as in create_class().
    """
    classes = cfg.get("classes") or []
    if not isinstance(classes, list) or not classes:
        return

    android_code = _decode_b64_text(cfg.get("nodes_handlers", "") or "")
    server_code = _decode_b64_text(cfg.get("nodes_server_handlers", "") or "")

    def has_class(code: str, name: str) -> bool:
        return f"class {name}(" in code

    # Android stub 
    def android_stub(name: str) -> str:
        return f"""
class {name}(Node):
    def __init__(self, modules, jNode, modulename, uid, _data):
        super().__init__(modules, jNode, modulename, uid, _data)

    \"\"\"Class {name}\"\"\"
"""

    # Server stub 
    def server_stub(name: str) -> str:
        return f"""
class {name}(Node):

    def __init__(self, node_id=None, config_uid=None):
        super().__init__(node_id, config_uid)
        # Additional initialization for {name}
"""

    for cls in classes:
        if not isinstance(cls, dict):
            continue
        name = (cls.get("name") or "").strip()
        if not name:
            continue

        if not has_class(android_code, name):
            android_code += "\n\n" + android_stub(name).lstrip("\n")

        if not has_class(server_code, name):
            server_code += "\n\n" + server_stub(name).lstrip("\n")

    cfg["nodes_handlers"] = _encode_b64_text(android_code)
    cfg["nodes_server_handlers"] = _encode_b64_text(server_code)


@app.route('/config/<uid>/ai-generate', methods=['POST'])
@login_required
def ai_generate(uid):
    config = db.session.execute(
        select(Configuration).where(
            Configuration.uid == uid,
            Configuration.user_id == current_user.id
        )
    ).scalar_one_or_none()

    if not config:
        abort(404)

    data = request.get_json() or {}
    prompt = (data.get('prompt') or '').strip()
    llm_provider = (data.get('llm') or 'deepseek').strip().lower()

    if not prompt:
        return jsonify({"status": "error", "message": "Empty prompt"}), 400

    try:
        # 1. Downloading the system prompt from GitHub
        llm_url = "https://raw.githubusercontent.com/dvdocumentation/nodalogic/refs/heads/main/LLM.txt"
        r = requests.get(llm_url, timeout=10)
        if r.status_code == 200:
            system_prompt = r.text
        else:
            system_prompt = "You are the NodaLogic configuration generation assistant. Always return valid JSON without any explanations."

        # 2. current configuration
        current_config_json = json.loads(get_config(config.uid))

        # 3. form a request to LLM:
        #    Request return the COMPLETE new configuration in the same JSON format.
        #3) STEP 1: Ask LLM for ONLY the JSON patch WITHOUT handlers.
        user_prompt_patch = (
            "User request:\n"
            f"{prompt}\n\n"
            "Below is the current configuration in JSON format.\n"
            "Return ONE JSON object of the SAME FORMAT as NodaLogic config, BUT DO NOT include:\n"
            "nodes_handlers, nodes_server_handlers.\n"
            "Return only changed/added: classes, datasets, sections, CommonEvents.\n"
            "Unchanged fields can be omitted. Do not delete anything unless explicitly asked.\n"
            "No comments, ONLY JSON.\n\n"
            "Current configuration:\n"
            f"{json.dumps(current_config_json, ensure_ascii=False, indent=2)}"
        )

        completion_text = call_llm(llm_provider, system_prompt, user_prompt_patch)
        json_str = extract_json_from_text(completion_text)
        llm_patch_data = json.loads(json_str)

        # Merge patch into current (handlers remain current for now—we'll update them in step 2)
        merged_config_data = merge_llm_config_into_current_ai(current_config_json, llm_patch_data)

        # 4) STEP 2: Generate handlers as CODE (body), and do base64 yourself
        # Android handlers
        current_android_code = _decode_b64_text(current_config_json.get("nodes_handlers", ""))
        android_header, android_body = _split_handlers_header_and_body(current_android_code)

        # If the header is empty (the marker wasn't found), we use the current one as "all immutable."
        # and the body is then empty: LLM will return the full file as the body (but we don't want that).
        # Therefore, we use a fallback: if the marker isn't found, immutable = ANDROID_IMPORTS_TEMPLATE + NODE_CLASS_CODE_ANDROID
        if not android_header:
            base_url = current_config_json.get("url", "")
            android_header = (ANDROID_IMPORTS_TEMPLATE.format(uid=config.uid, config_url=base_url) + "\n" + NODE_CLASS_CODE_ANDROID.strip() + "\n")
            # body — the current code without the header (if any), otherwise the entire code
            android_body = android_body or ""

        new_android_body = _generate_handlers_body_ai(
            provider=llm_provider,
            system_prompt=system_prompt,
            user_request=prompt,
            merged_config_json=merged_config_data,
            current_header=android_header,
            current_body=android_body,
            kind_label="ANDROID",
            max_attempts=3,
        )
        new_android_full = (android_header.rstrip() + "\n\n" + new_android_body.strip() + "\n")
        merged_config_data["nodes_handlers"] = _encode_b64_text(new_android_full)

        # Server handlers (if used; if empty, you can leave it empty or also generate it)
        current_server_code = _decode_b64_text(current_config_json.get("nodes_server_handlers", ""))
        server_header, server_body = _split_handlers_header_and_body(current_server_code)

        if current_config_json.get("nodes_server_handlers") or server_header or server_body:
            if not server_header:
                
                server_header = (NODE_CLASS_CODE.strip() + "\n")
                server_body = server_body or ""

            new_server_body = _generate_handlers_body_ai(
                provider=llm_provider,
                system_prompt=system_prompt,
                user_request=prompt,
                merged_config_json=merged_config_data,
                current_header=server_header,
                current_body=server_body,
                kind_label="SERVER",
                max_attempts=3,
            )
            new_server_full = (server_header.rstrip() + "\n\n" + new_server_body.strip() + "\n")
            merged_config_data["nodes_server_handlers"] = _encode_b64_text(new_server_full)

        # 5) Final validation of the entire configuration (including syntax + UI types)
        config_url = url_for('get_config', uid=config.uid, _external=True)

        # 1) ensure basic headers/skeleton handlers (with ANDROID_IMPORTS_TEMPLATE)
        ensure_handlers_skeleton_and_headers(config.uid, config_url, merged_config_data)

        # 2) We guarantee classes from JSON in both handlers (even if LLM “forgot”)
        ensure_all_classes_present_in_handlers(merged_config_data)

        errors = validate_full_llm_config_ai(merged_config_data)

        # Retry up to 3 times: fix patch+body handlers (leave the header alone)
        attempts = 1
        while errors and attempts < 3:
            attempts += 1

            fix_prompt_patch = (
                "Your configuration PATCH did NOT validate.\n"
                "Fix ONLY the errors below.\n"
                "Return ONE JSON object (PATCH) with only: classes, datasets, sections, CommonEvents.\n"
                "DO NOT include nodes_handlers/nodes_server_handlers in this JSON.\n"
                "No comments, ONLY JSON.\n\n"
                "Errors:\n- " + "\n- ".join(errors) + "\n\n"
                "Previous PATCH JSON:\n"
                + json.dumps(llm_patch_data, ensure_ascii=False, indent=2)
            )

            completion_text = call_llm(llm_provider, system_prompt, fix_prompt_patch)
            json_str = extract_json_from_text(completion_text)
            llm_patch_data = json.loads(json_str)

            merged_config_data = merge_llm_config_into_current_ai(current_config_json, llm_patch_data)

            config_url = url_for('get_config', uid=config.uid, _external=True)
            ensure_handlers_skeleton_and_headers(config.uid, config_url, merged_config_data)
            ensure_all_classes_present_in_handlers(merged_config_data)

            # regen ANDROID body with knowledge of errors
            new_android_body = _generate_handlers_body_ai(
                provider=llm_provider,
                system_prompt=system_prompt,
                user_request=prompt + "\n\nValidation errors to fix:\n- " + "\n- ".join(errors),
                merged_config_json=merged_config_data,
                current_header=android_header,
                current_body=android_body,
                kind_label="ANDROID",
                max_attempts=3,
            )
            new_android_full = (android_header.rstrip() + "\n\n" + new_android_body.strip() + "\n")
            merged_config_data["nodes_handlers"] = _encode_b64_text(new_android_full)

            # regen SERVER body if it exists/used
            if current_config_json.get("nodes_server_handlers") or server_header or server_body:
                new_server_body = _generate_handlers_body_ai(
                    provider=llm_provider,
                    system_prompt=system_prompt,
                    user_request=prompt + "\n\nValidation errors to fix:\n- " + "\n- ".join(errors),
                    merged_config_json=merged_config_data,
                    current_header=server_header,
                    current_body=server_body,
                    kind_label="SERVER",
                    max_attempts=3,
                )
                new_server_full = (server_header.rstrip() + "\n\n" + new_server_body.strip() + "\n")
                merged_config_data["nodes_server_handlers"] = _encode_b64_text(new_server_full)

            config_url = url_for('get_config', uid=config.uid, _external=True)
            ensure_handlers_skeleton_and_headers(config.uid, config_url, merged_config_data)
            ensure_all_classes_present_in_handlers(merged_config_data)

            errors = validate_full_llm_config_ai(merged_config_data)

        if errors:
            return jsonify({
                "status": "error",
                "message": "AI generation failed validation:\n- " + "\n- ".join(errors)
            }), 400

        

        new_config_data = merged_config_data

        

    except Exception as e:
        #current_app.logger.exception("AI generator error")
        return jsonify({
            "status": "error",
            "message": f"An error occurred while requesting LLM or parsing the response.: {e}"
        }), 500

    try:
        apply_full_config_from_json(config, new_config_data)
        db.session.commit()
        return jsonify({
            "status": "ok",
            "message": "Configuration successfully updated via AI generator"
        })
    except Exception as e:
        db.session.rollback()
        #current_app.logger.exception("AI generator apply config error")
        return jsonify({
            "status": "error",
            "message": f"Error applying configuration: {e}"
        }), 500

@app.route('/config/<uid>/ai-generate-layout', methods=['POST'])
@login_required
def ai_generate_layout(uid):
    """Generate ONLY a UI layout JSON (2D array) for copy/paste.
    Does NOT apply anything to the configuration.
    """
    config = db.session.execute(
        select(Configuration).where(
            Configuration.uid == uid,
            Configuration.user_id == current_user.id
        )
    ).scalar_one_or_none()

    if not config:
        abort(404)

    data = request.get_json() or {}
    prompt = (data.get('prompt') or '').strip()
    llm_provider = (data.get('llm') or 'deepseek').strip().lower()

    if not prompt:
        return jsonify({"status": "error", "message": "Empty prompt"}), 400

    try:
        # system prompt 
        llm_url = "https://raw.githubusercontent.com/dvdocumentation/nodalogic/refs/heads/main/LLM.txt"
        r = requests.get(llm_url, timeout=10)
        if r.status_code == 200:
            system_prompt = r.text
        else:
            system_prompt = "You are the NodaLogic configuration generation assistant. Always return valid JSON without any explanations."

        
        current_config_json = json.loads(get_config(config.uid))

        allowed = sorted(ALLOWED_UI_TYPES_AI)
        allowed_inputs = sorted(ALLOWED_INPUT_TYPES_AI)

        user_prompt = (
            "Generate ONLY a UI layout JSON for NodaLogic.\n"
            "Return ONLY a JSON ARRAY, no comments, no markdown.\n\n"
            "Format requirements:\n"
            "- Root is a list of ROWS\n"
            "- Each row is a list of element objects (dict)\n"
            "- Each element MUST have a CASE-SENSITIVE field: type\n"
            "- If you use container types (VerticalLayout/HorizontalLayout/VerticalScroll/HorizontalScroll/Card), put nested layout into value as a list of rows\n"
            "- If you use Table, put nested layout into layout as a list of rows\n\n"
            f"Allowed types: {allowed}\n"
            f"Allowed Input.input_type (if present): {allowed_inputs}\n\n"
            "User request:\n"
            f"{prompt}\n\n"
           # "Current configuration (for names/reference; do not return it):\n"
           # f"{json.dumps(current_config_json, ensure_ascii=False, indent=2)}"
        )

        completion_text = call_llm(llm_provider, system_prompt, user_prompt)
        json_arr_str = extract_json_array_from_text(completion_text)
        layout = json.loads(json_arr_str)

        # Validate basic structure + allowed UI types
        errors = []
        if not isinstance(layout, list):
            errors.append("layout root must be a list")
        else:
            for i, row in enumerate(layout):
                if not isinstance(row, list):
                    errors.append(f"layout[{i}] must be a list (row)")

        errors.extend(validate_layout_types_ai(layout, where="layout"))

        if errors:
            return jsonify({
                "status": "error",
                "message": "Generated layout failed validation:\n- " + "\n- ".join(errors),
            }), 400

        return jsonify({
            "status": "ok",
            "layout": layout,
            "layout_pretty": json.dumps(layout, ensure_ascii=False, indent=2),
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"An error occurred while generating layout: {e}",
        }), 500


@app.route('/api/room/<room_uid>/task/<task_uid>', methods=['GET'])
@api_auth_required
def get_task(room_uid, task_uid):
    with SqliteDict(TASKS_DB_PATH) as tasks_db:
        tasks = tasks_db.get(room_uid, [])
        for i, task in enumerate(tasks):
            if task.get('uid') == task_uid:
                if task.get('_blocked'):
                    return jsonify({
                        'status': 'error',
                        'message': 'Task already blocked'
                    }), 400
                
                
                tasks[i]['_blocked'] = True
                tasks[i]['_blocked_at'] = datetime.now().isoformat()
                tasks_db[room_uid] = tasks
                tasks_db.commit()
                
                
                send_tasks_update(room_uid)
                
                return jsonify({
                    'status': 'success',
                    'task': task
                })
    
    return jsonify({'status': 'error', 'message': 'Task not found'}), 404

def handle_ws_command(room_uid, user, data, auth_success):
    command = data.get('type')
    
    if not (command == "debug" or command == "get_users"):
        if not auth_success==True:
            return


    if command == 'get_task':
        # Task reservation logic
        with app.app_context():  
            with SqliteDict(TASKS_DB_PATH) as tasks_db:
                tasks = tasks_db.get(room_uid, [])
                for task in tasks:
                    if task.get('uid') == data.get('task_uid') and not task.get('_blocked'):
                        task['_blocked'] = True
                        task['_blocked_by'] = user
                        task['_blocked_at'] = datetime.now().isoformat()
                        tasks_db[room_uid] = tasks
                        tasks_db.commit()
                        
                        ws = active_connections[room_uid].get(user)
                        if ws:
                            ws.send(json.dumps({
                                'type': 'task_assigned',
                                'task': task
                            }))
                        send_tasks_update(room_uid)
                        return
                        
                # If the task is not found
                ws = active_connections[room_uid].get(user)
                if ws:
                    ws.send(json.dumps({
                        'type': 'error',
                        'message': 'Task not available'
                    }))
    elif command == 'get_users':
        # Send a list of all connected users
        users_list = get_connected_users(room_uid)
        ws = active_connections[room_uid].get(user)
        if ws and not ws.closed:
            ws.send(json.dumps({
                'type': 'users_update',
                'users': users_list
            }))                
    elif command == 'acknowledge_objects':
        # The client confirms receipt of the objects
        object_ids = data.get('object_ids', [])
        
        with app.app_context():
            for obj_id in object_ids:
                room_object = db.session.get(RoomObjects, obj_id)
                if room_object and room_object.room_uid == room_uid:
                    # Add the user to the list of confirmed users
                    acknowledged = room_object.acknowledged_by or []
                    if user not in acknowledged:
                        acknowledged.append(user)
                        room_object.acknowledged_by = acknowledged
                        
                        # If all connected clients have confirmed, the object can be deleted
                        active_users = list(active_connections[room_uid].keys()) if room_uid in active_connections else []
                        if set(acknowledged) == set(active_users) and active_users:
                            db.session.delete(room_object)
            
            db.session.commit()
            
            # Send confirmation to the client
            ws = active_connections[room_uid].get(user)
            if ws:
                ws.send(json.dumps({
                    'type': 'acknowledgment_confirmed',
                    'object_ids': object_ids
                }))
    elif command == 'remote_method_response':
        # Processing the response from the remote method
        request_id = data.get('request_id')
        result_data = data.get('data', {})
        error = data.get('error')
        
        # Save the result for the corresponding query
        if request_id in pending_responses:
            pending_responses[request_id]['completed'] = True
            pending_responses[request_id]['result'] = result_data
            pending_responses[request_id]['error'] = error
    
    elif command == 'get_objects':
       # Client requests objects
        config_uid = data.get('config_uid')
        class_name = data.get('class_name')
        since = data.get('since')
        
        with app.app_context():
            query = RoomObjects.query.filter_by(room_uid=room_uid)
            
            #if config_uid:
            #    query = query.filter_by(config_uid=config_uid)
            #if class_name:
            #    query = query.filter_by(class_name=class_name)
            #if since:
            #    try:
            #        since_date = datetime.fromisoformat(since.replace('Z', '+00:00'))
            #        query = query.filter(RoomObjects.created_at > since_date)
            #    except ValueError:
            #        pass
            
            objects = query.order_by(RoomObjects.created_at.desc()).all()
            
            ws = active_connections[room_uid].get(user)
            if ws:
                objects_data = []
                for obj in objects:
                    objects_data.append({
                        'config_uid': obj.config_uid,
                        'class_name': obj.class_name,
                        'objects': obj.objects_data,
                        'created_at': obj.created_at.isoformat()
                    })
                
                ws.send(json.dumps({
                    'type': 'objects_response',
                    'objects': objects_data
                }))
    elif command == 'debug':
        description = data.get("description")
        node_id = data.get("node_id")
        node_data = data.get("node_data")
        
        # Send a debug message to all connected clients
        if room_uid in active_connections:
            debug_message = {
                'type': 'debug',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'description': description,
                'node_id': node_id,
                'node_data': node_data,
                'user': user
            }
            
            for conn_user, ws in list(active_connections[room_uid].items()):
                try:
                    if not ws.closed:
                        ws.send(json.dumps(debug_message))
                except WebSocketError:
                    active_connections[room_uid].pop(conn_user, None)

@app.context_processor
def utility_processor():
    def safe_getattr(obj, attr, default=None):
        return getattr(obj, attr, default)
    return dict(safe_getattr=safe_getattr)

@app.before_request
def before_request():
    # Set the user's time zone (can be saved in the user settings)
    g.user_timezone = pytz.timezone('Europe/Moscow')  



@app.after_request
def update_config_timestamp(response):
    if request.endpoint in ['add_method', 'delete_method', 'edit_method', 
                          'add_event', 'edit_event', 'edit_class']:
        class_id = request.view_args.get('class_id')
        if class_id:
            class_obj = db.session.get(ConfigClass, class_id)
            if class_obj:
                class_obj.config.update_last_modified()
    return response    

def get_user_local_time():
    return datetime.now(g.user_timezone)

from ast import parse, FunctionDef, fix_missing_locations
import ast
import io

@app.route('/get-method-body')
@login_required
def get_method_body():
    class_id = request.args.get('class_id')
    method_name = request.args.get('method_name')
    engine = request.args.get('engine')
    
    class_obj = db.session.get(ConfigClass, class_id)
    if not class_obj or class_obj.config.user_id != current_user.id:
        abort(404)
    
    
    if engine == 'server_python' and class_obj.config.nodes_server_handlers:
        try:
            module_code = base64.b64decode(class_obj.config.nodes_server_handlers).decode('utf-8')
            body = extract_method_body_from_code(module_code, class_obj.name, method_name)
            
            if body is None:
               
                method_obj = next((m for m in class_obj.methods 
                                 if m.code == method_name and m.engine == 'server_python'), None)
                if method_obj:
                    
                    return jsonify({'body': '', 'warning': 'Method not found in code'})
                else:
                    return jsonify({'body': '', 'error': 'The method does not exist'})
            
            return jsonify({'body': body})
        except Exception as e:
            return jsonify({'body': '', 'error': str(e)})
    
   
    elif engine == 'android_python' and class_obj.config.nodes_handlers:
        try:
            module_code = base64.b64decode(class_obj.config.nodes_handlers).decode('utf-8')
            body = extract_method_body_from_code(module_code, class_obj.name, method_name)
            
            if body is None:
               
                method_obj = next((m for m in class_obj.methods 
                                 if m.code == method_name and m.engine == 'android_python'), None)
                if method_obj:
                    
                    return jsonify({'body': '', 'warning': 'Method not found in code'})
                else:
                    return jsonify({'body': '', 'error': 'The method does not exist'})
            
            return jsonify({'body': body})
        except Exception as e:
            return jsonify({'body': '', 'error': str(e)})
    
    return jsonify({'body': ''})

def remove_example_method_from_class(module_code, class_name):
   
    lines = module_code.split('\n')
    class_start = -1
    class_indent = 0
    
    # Looking for the beginning of the class
    for i, line in enumerate(lines):
        if line.strip().startswith(f'class {class_name}('):
            class_start = i
            class_indent = len(line) - len(line.lstrip())
            break
    
    if class_start == -1:
        return module_code
    
    # Search for example_method
    example_start = -1
    example_end = -1
    in_example = False
    
    for i in range(class_start + 1, len(lines)):
        line = lines[i]
        current_indent = len(line) - len(line.lstrip())
        
        if current_indent <= class_indent and line.strip():
            # End of class
            break
        
        if line.strip().startswith('def example_method('):
            example_start = i
            in_example = True
            continue
        
        if in_example and current_indent == class_indent + 4:
            # Still inside the method
            continue
        
        if in_example and current_indent <= class_indent:
            # End of method
            example_end = i
            break
    
    if example_start != -1:
        if example_end == -1:
            example_end = len(lines)
        
        # Remove example_method
        new_lines = lines[:example_start] + lines[example_end:]
        return '\n'.join(new_lines)
    
    return module_code
    

@app.route('/save-method/<int:method_id>', methods=['POST'])
@login_required
def save_method(method_id):
    method = db.session.get(ClassMethod, method_id)
    if not method or method.class_obj.config.user_id != current_user.id:
        abort(404)
    
    method.name = request.form['name']
    method.source = request.form['source']
    method.engine = request.form['engine']
    method.code = request.form['name']
    
   
    function_body = request.form['function_body']
    
    try:
        
        if method.engine == 'server_python':
            current_module = ""
            if method.class_obj.config.nodes_server_handlers:
                current_module = base64.b64decode(method.class_obj.config.nodes_server_handlers).decode('utf-8')
            
            
            new_module = add_method_to_class(current_module, method.class_obj.name, method.name, function_body)
            
            if new_module is None:  
                return redirect(url_for('edit_class', class_id=method.class_id, _anchor='handlers-refresh'))
            
            
            method.class_obj.config.nodes_server_handlers = base64.b64encode(new_module.encode('utf-8')).decode('utf-8')
            
           
            handlers_dir = os.path.join('Handlers', method.class_obj.config.uid)
            os.makedirs(handlers_dir, exist_ok=True)
            handlers_file_path = os.path.join(handlers_dir, 'handlers.py')
            with open(handlers_file_path, 'w', encoding='utf-8') as f:
                f.write(new_module)
        
        
        elif method.engine == 'android_python':
            current_module = ""
            if method.class_obj.config.nodes_handlers:
                current_module = base64.b64decode(method.class_obj.config.nodes_handlers).decode('utf-8')
            
            
            new_module = add_method_to_class(current_module, method.class_obj.name, method.name, function_body)
            
            if new_module is None:  
                return redirect(url_for('edit_class', class_id=method.class_id, _anchor='handlers-refresh'))
            
            
            method.class_obj.config.nodes_handlers = base64.b64encode(new_module.encode('utf-8')).decode('utf-8')
        
        method.class_obj.config.update_last_modified()
        db.session.commit()
        flash(_('Method saved successfully'), 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(_('Save error: ')+ str(e), 'danger')
    
    return redirect(url_for('edit_class', class_id=method.class_id, _anchor='handlers-refresh'))

@app.route('/update-config/<uid>', methods=['POST'])
@login_required
def update_config(uid):
    config = Configuration.query.filter_by(uid=uid, user_id=current_user.id).first_or_404()
    
    if 'name' in request.form:
        config.name = request.form['name']
    if 'version' in request.form:
        config.version = request.form['version']
    if 'server_name' in request.form: 
        config.server_name = request.form['server_name']    
    

    config.last_modified = get_user_local_time()
    db.session.commit()
    
    flash(_('Configuration updated'), 'success')
    active_tab = request.form.get("active_tab", "config")
    return redirect(url_for('edit_config', uid=uid,tab=active_tab))


@app.route('/update-handlers-code/<uid>', methods=['POST'])
@login_required
def update_handlers_code(uid):
    config = db.session.scalars(
        select(Configuration)
        .where(Configuration.uid == uid, Configuration.user_id == current_user.id)
    ).first()
    
    if not config:
        abort(404)
    
    handlers_code = request.form.get('handlers_code', '')
    
    if not handlers_code:
        flash(_('Empty handler code received'), 'danger')
        active_tab = request.form.get("active_tab", "config")
        return redirect(url_for('edit_config', uid=uid,tab=active_tab))
    
    try:
        
        is_valid, error = validate_python_syntax(handlers_code)
        if not is_valid:
            
            flash(_('Python syntax error')+error, 'danger')
            active_tab = request.form.get("active_tab", "config")
            
            return jsonify({"status": "error", "message": _('Python syntax error')+error })
        
        android_imports = ANDROID_IMPORTS_TEMPLATE.format(
            uid=config.uid, 
            config_url=url_for('get_config', uid=config.uid, _external=True)
        )
        
        
        if 'from nodes import Node' not in handlers_code:
            
            handlers_code = android_imports + NODE_CLASS_CODE_ANDROID + '\n' + handlers_code
            is_valid, error = validate_python_syntax(handlers_code)
            if not is_valid:
                flash(_('Syntax error after adding imports:')+error, 'danger')
                active_tab = request.form.get("active_tab", "config")
                #return redirect(url_for('edit_config', uid=uid, tab=active_tab))
                return jsonify({"status": "error", "message": _('Syntax error after adding imports:')+error})


        encoded = base64.b64encode(handlers_code.encode('utf-8')).decode('utf-8')
        config.nodes_handlers = encoded
        config.update_last_modified()
        db.session.commit()
        
        
        sync_classes_from_android_handlers(config)
        sync_methods_from_code(config)
        #from flask import session
        #session['_flashes'] = []
        session.modified = True
        flash(_('Code saved successfully'), 'success')
    except Exception as e:
        db.session.rollback()
        #print(f"Error saving code: {str(e)}")
        flash(_('Save error:') +str(e), 'error')
        return redirect(url_for("edit_config", uid=config.uid, tab="handlers", subtab="code"))
        
    active_tab = request.form.get("active_tab", "config")
    #return redirect(url_for('edit_config', uid=uid, tab=active_tab))
    return jsonify({"status": "ok"})

#Datasets API
@app.route('/api/config/<uid>/dataset/<dataset_name>/items', methods=['GET'])
@api_auth_required
def get_dataset_items(uid, dataset_name):
    config = db.session.execute(
        select(Configuration).where(Configuration.uid == uid)
    ).scalar_one_or_none()
    
    if not config:
        abort(404)
    
    dataset = next((d for d in config.datasets if d.name == dataset_name), None)
    if not dataset:
        abort(404)
    
    items = []
    for item in dataset.items:
        item_data = item.data.copy()  
        item_data['_id'] = item.item_id 
        items.append(item_data)
    return jsonify(items)

@app.route('/get-dataset-json')
@login_required
def get_dataset_json():
    dataset_id = request.args.get('dataset_id')
    dataset = db.session.get(Dataset, dataset_id)
    
    if not dataset or dataset.config.user_id != current_user.id:
        abort(404)
    
    return jsonify({
        'name': dataset.name,
        'hash_indexes': dataset.hash_indexes,
        'text_indexes': dataset.text_indexes,
        'view_template': dataset.view_template,
        'autoload': dataset.autoload
    })

@app.route('/api/config/<uid>/dataset/<dataset_name>/items', methods=['DELETE'])
@api_auth_required
def delete_all_dataset_items(uid, dataset_name):
    """Delete all records from the dataset"""
    config = db.session.execute(
        select(Configuration).where(Configuration.uid == uid)
    ).scalar_one_or_none()
    
    if not config:
        abort(404)
    
    dataset = next((d for d in config.datasets if d.name == dataset_name), None)
    if not dataset:
        abort(404)
    
    try:
        
        deleted_count = DatasetItem.query.filter_by(dataset_id=dataset.id).delete()
        db.session.commit()
        
        return jsonify({
            "status": "success", 
            "message": f"Deleted {deleted_count} items",
            "deleted_count": deleted_count
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/api/config/<uid>/dataset/<dataset_name>/items/<item_id>', methods=['DELETE'])
@api_auth_required
def delete_dataset_item(uid, dataset_name, item_id):
    """Delete a specific record from a dataset by ID"""
    config = db.session.execute(
        select(Configuration).where(Configuration.uid == uid)
    ).scalar_one_or_none()
    
    if not config:
        abort(404)
    
    dataset = next((d for d in config.datasets if d.name == dataset_name), None)
    if not dataset:
        abort(404)
    
    
    item = DatasetItem.query.filter_by(dataset_id=dataset.id, item_id=item_id).first()
    if not item:
        return jsonify({"error": "Item not found"}), 404
    
    try:
        db.session.delete(item)
        db.session.commit()
        
        return jsonify({
            "status": "success", 
            "message": f"Item {item_id} deleted"
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/api/config/<uid>/dataset/<dataset_name>/items', methods=['POST'])
@api_auth_required
def add_dataset_items(uid, dataset_name):
    config = db.session.execute(
        select(Configuration).where(Configuration.uid == uid)
    ).scalar_one_or_none()
    
    if not config:
        abort(404)
    
    dataset = next((d for d in config.datasets if d.name == dataset_name), None)
    if not dataset:
        abort(404)
    
    items = request.get_json()
    
    if not isinstance(items, list):
        abort(400, description="Request body must be a JSON array")
    
    for item in items:
        if not isinstance(item, dict):
            continue
            
        item_id = item.get('_id')
        if '_id' not in item:
            item['_id'] = str(uuid.uuid4())
            
        item_id = item['_id']
            
        # Check if item already exists
        existing_item = DatasetItem.query.filter_by(dataset_id=dataset.id, item_id=item_id).first()
        
        if existing_item:
            # Update existing item
            existing_item.data = item
            existing_item.updated_at = datetime.now(timezone.utc)
        else:
            # Create new item
            new_item = DatasetItem(
                dataset_id=dataset.id,
                item_id=item_id,
                data=item
            )
            db.session.add(new_item)
    
    db.session.commit()
    return jsonify({"status": "success", "count": len(items)})

#Datasets - UI
# Add these routes for dataset management in the UI
@app.route('/add-dataset/<config_uid>', methods=['POST'])
@login_required
def add_dataset(config_uid):
    config = db.session.scalars(
        select(Configuration)
        .where(Configuration.uid == config_uid, Configuration.user_id == current_user.id)
    ).first()
    
    if not config:
        abort(404)
    
    name = request.form.get('name')
    hash_indexes = request.form.get('hash_indexes', '')
    text_indexes = request.form.get('text_indexes', '')
    view_template = request.form.get('view_template', '')
    autoload = 'autoload' in request.form  # Check if checkbox was checked
    
    if name:
        new_dataset = Dataset(
            name=name,
            hash_indexes=hash_indexes,
            text_indexes=text_indexes,
            view_template=view_template,
            autoload=autoload,
            config_id=config.id
        )
        db.session.add(new_dataset)
        db.session.commit()
    
    return jsonify({
            "status": "success",
            "message": "Dataset created",
            "dataset": {
                "id": new_dataset.id,
                "name": new_dataset.name
            }
        })

@app.route('/get-section-json')
@login_required
def get_section_json():
    section_id = request.args.get('section_id')
    section = db.session.get(ConfigSection, section_id)
    
    if not section or section.config.user_id != current_user.id:
        abort(404)
    
    return jsonify({
        'id': section.id,
        'code': section.code,
        'name': section.name,
        'commands': section.commands
    })

@app.route('/edit-dataset/<dataset_id>', methods=['GET', 'POST'])
@login_required
def edit_dataset(dataset_id):
    dataset = db.session.get(Dataset, dataset_id)
    if not dataset or dataset.config.user_id != current_user.id:
        abort(404)

    if request.method == 'POST':
        dataset.name = request.form.get('name')
        dataset.hash_indexes = request.form.get('hash_indexes', '')
        dataset.text_indexes = request.form.get('text_indexes', '')
        dataset.view_template = request.form.get('view_template', '')
        dataset.autoload = 'autoload' in request.form
        db.session.commit()
        flash(_('Dataset updated successfully'), 'success')
        #active_tab = request.form.get("active_tab", "datasets")
        active_tab = "datasets"
        return redirect(url_for('edit_config', uid=dataset.config.uid,tab=active_tab))

    return render_template('edit_dataset.html', dataset=dataset)

@app.route('/update-dataset/<dataset_id>', methods=['POST'])
@login_required
def update_dataset(dataset_id):
    dataset = db.session.get(Dataset, dataset_id)
    if not dataset or dataset.config.user_id != current_user.id:
        abort(404)

    # Getting the active tab from the form
    active_tab = request.form.get('active_tab', 'datasets')
    
    dataset.name = request.form.get('name')
    dataset.hash_indexes = request.form.get('hash_indexes', '')
    dataset.text_indexes = request.form.get('text_indexes', '')
    dataset.view_template = request.form.get('view_template', '')
    dataset.autoload = 'autoload' in request.form
    db.session.commit()

    # Returning JSON with the URL for redirection
    return jsonify({
        "status": "success",
        "message": "Dataset updated",
        "redirect_url": url_for('edit_config', uid=dataset.config.uid, tab=active_tab),
        "dataset": {
            "id": dataset.id,
            "name": dataset.name
        }
    })

@app.route('/delete-dataset/<dataset_id>')
@login_required
def delete_dataset(dataset_id):
    dataset = db.session.get(Dataset, dataset_id)
    if not dataset or dataset.config.user_id != current_user.id:
        abort(404)
    
    config_uid = dataset.config.uid
    db.session.delete(dataset)
    db.session.commit()
    #active_tab = request.form.get("active_tab", "datasets")
    active_tab = "datasets"
    return redirect(url_for('edit_config', uid=config_uid,tab=active_tab))

#Sections
@app.route('/add-section/<config_uid>', methods=['POST'])
@login_required
def add_section(config_uid):
    config = db.session.scalars(
        select(Configuration)
        .where(Configuration.uid == config_uid, Configuration.user_id == current_user.id)
    ).first()

    
    if not config:
        abort(404)
    
    code = request.form.get('code')
    name = request.form.get('name')
    commands = request.form.get('commands', '')
    
    if code and name:
        new_section = ConfigSection(
            code=code,
            name=name,
            commands=commands,
            config_id=config.id
        )
        db.session.add(new_section)
        db.session.commit()
        return jsonify({"status": "success"})
    
    return jsonify({"status": "error", "message": "No code or name specified"}), 400

@app.route('/update-section/<section_id>', methods=['POST'])
@login_required
def update_section(section_id):
    section = db.session.get(ConfigSection, section_id)
    if not section or section.config.user_id != current_user.id:
        abort(404)
    
    section.code = request.form.get('code')
    section.name = request.form.get('name')
    section.commands = request.form.get('commands', '')
    db.session.commit()
    
    return jsonify({"status": "success"})

@app.route('/delete-section/<section_id>')
@login_required
def delete_section(section_id):
    section = db.session.get(ConfigSection, section_id)
    if not section or section.config.user_id != current_user.id:
        abort(404)
    
    config_uid = section.config.uid
    db.session.delete(section)
    db.session.commit()
    active_tab = request.form.get("active_tab", "config")
    return redirect(url_for('edit_config', uid=config_uid,tab =active_tab))


@app.route('/debug-room/<room_uid>')
@login_required
def debug_room(room_uid):
    room = Room.query.filter_by(uid=room_uid, user_id=current_user.id).first_or_404()
    
    #ws_url = f"wss://{request.host}/ws?room={room.uid}"
    ws_scheme = get_ws_scheme()
    ws_url = f"{ws_scheme}://{request.host}/ws?room={room.uid}"
    qr_img = generate_qr_code(ws_url)
    
    return render_template('debug_room.html', 
                         room=room,
                         ws_url=ws_url,
                         qr_img=qr_img)

@app.route('/create-debug-room', methods=['POST'])
@login_required
def create_debug_room():
    name = request.form.get('name', 'Debug room')
    new_room = Room(
        name=name,
        user_id=current_user.id
    )
    db.session.add(new_room)
    db.session.commit()
    return redirect(url_for('debug_room', room_uid=new_room.uid))


def sync_classes_from_server_handlers(config):
    """Synchronizes classes from server handlers with the database"""
    if not config.nodes_server_handlers:
        return
    
    try:
        module_code = base64.b64decode(config.nodes_server_handlers).decode('utf-8')
        tree = ast.parse(module_code)
        
        # We are looking for all classes that inherit from Node
        node_classes = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Check if it inherits from Node
                for base in node.bases:
                    if (isinstance(base, ast.Name) and base.id == 'Node') or \
                       (isinstance(base, ast.Attribute) and base.attr == 'Node'):
                        # Exclude the Node class itself
                        if node.name != 'Node':
                            node_classes.append(node.name)
                        break
        
        # Synchronize with the database
        existing_classes = {c.name: c for c in config.classes}
        
        for class_name in node_classes:
            if class_name not in existing_classes:
                # Create a new class in the database
                new_class = ConfigClass(
                    name=class_name,
                    display_name=class_name,
                    config_id=config.id,
                    class_type='custom_process',
                    section_code='server'
                )
                db.session.add(new_class)
                #print(f"Added new class from code: {class_name}")
        
        # We remove only server classes that are not in the code
        for class_name, class_obj in existing_classes.items():
            if (class_name not in node_classes and 
                class_obj.section_code == 'server' and
                class_obj.name != 'Node'):
                db.session.delete(class_obj)
                print(f"Removed class not in code: {class_name}")
        
        db.session.commit()
        
    except Exception as e:
        print(f"Error syncing classes from server handlers: {str(e)}")


@app.route('/config/<uid>/upload-server-handlers', methods=['POST'])
@login_required
def upload_server_handlers(uid):
    config = Configuration.query.filter_by(uid=uid, user_id=current_user.id).first_or_404()
    
    upload_type = request.form.get('upload_type')
    handlers_code = ''
    
    if upload_type == 'file':
        file = request.files['python_file']
        if file and file.filename.endswith('.py'):
            handlers_code = file.read().decode('utf-8')
    
    elif upload_type == 'github':
        github_url = request.form.get('github_url')
        try:
            response = requests.get(github_url)
            response.raise_for_status()
            handlers_code = response.text
        except Exception as e:
            flash(_('GitHub load error:')+str(e), 'error')
            active_tab = request.form.get("active_tab", "config")
            return redirect(url_for('edit_config', uid=uid, tab=active_tab))
    
    
    config.nodes_server_handlers = base64.b64encode(handlers_code.encode('utf-8')).decode('utf-8')
    db.session.commit()
    
    
    sync_classes_from_server_handlers(config)
    sync_methods_from_code(config)
    
    
    handlers_dir = os.path.join('Handlers', config.uid)
    os.makedirs(handlers_dir, exist_ok=True)
    handlers_file_path = os.path.join(handlers_dir, 'handlers.py')
    with open(handlers_file_path, 'w', encoding='utf-8') as f:
        f.write(handlers_code)
    
    flash(_('Server handlers loaded successfully'), 'success')
    active_tab = request.form.get("active_tab", "config")
    return redirect(url_for('edit_config', uid=uid, tab=active_tab))

@app.route('/config/<uid>/download-server-handlers')
@login_required
def download_server_handlers(uid):
    config = Configuration.query.filter_by(uid=uid, user_id=current_user.id).first_or_404()
    
    if not config.nodes_server_handlers:
        flash(_('No server handlers available for download'), 'error')
        active_tab = request.form.get("active_tab", "config")
        return redirect(url_for('edit_config', uid=uid,tab=active_tab))
    
    handlers_code = base64.b64decode(config.nodes_server_handlers).decode('utf-8')
    
    response = make_response(handlers_code)
    response.headers['Content-Type'] = 'text/x-python'
    response.headers['Content-Disposition'] = f'attachment; filename=server_handlers_{config.uid}.py'
    
    return response

@app.route('/config/<uid>/clear-server-handlers', methods=['POST'])
@login_required
def clear_server_handlers(uid):
    config = Configuration.query.filter_by(uid=uid, user_id=current_user.id).first_or_404()
    
    config.nodes_server_handlers = None
    db.session.commit()
    
    
    handlers_file_path = os.path.join('Handlers', config.uid, 'handlers.py')
    if os.path.exists(handlers_file_path):
        os.remove(handlers_file_path)
    
    flash(_('Server handlers deleted'), 'success')
    active_tab = request.form.get("active_tab", "config")
    return redirect(url_for('edit_config', uid=uid, tab=active_tab))

@app.route('/update-server-handlers-code/<uid>', methods=['POST'])
@login_required
def update_server_handlers_code(uid):
    config = db.session.scalars(
        select(Configuration)
        .where(Configuration.uid == uid, Configuration.user_id == current_user.id)
    ).first()
    
    if not config:
        abort(404)
    
    handlers_code = request.form.get('handlers_code', '')
    
    if not handlers_code:
        flash(_('Empty server handler code received'), 'danger')
        active_tab = request.form.get("active_tab", "config")
        return redirect(url_for('edit_config', uid=uid, tab=active_tab))
    
    try:
        
        is_valid, error = validate_python_syntax(handlers_code)
        if not is_valid:
            flash(_('Python syntax error')+error, 'danger')
            active_tab = request.form.get("active_tab", "config")
            return jsonify({"status": "error", "message": _('Python syntax error')+error })

        

        
        encoded = base64.b64encode(handlers_code.encode('utf-8')).decode('utf-8')
        config.nodes_server_handlers = encoded
        config.update_last_modified()
        db.session.commit()
        
        
        handlers_dir = os.path.join('Handlers', config.uid)
        os.makedirs(handlers_dir, exist_ok=True)
        
        handlers_file_path = os.path.join(handlers_dir, 'handlers.py')
        with open(handlers_file_path, 'w', encoding='utf-8') as f:
            f.write(handlers_code)
        
        
        sync_classes_from_server_handlers(config)
        sync_methods_from_code(config)
        
        session.modified = True
        flash(_('Server handler code saved successfully'), 'success')
    except Exception as e:
        db.session.rollback()
        #print(f"Error saving server handlers code: {str(e)}")
        flash(_('Server handler save error:')+str(e), 'error')
        return redirect(url_for("edit_config", uid=config.uid, tab="handlers-server", subtab="code"))
        
    active_tab = request.form.get("active_tab", "config")
    return jsonify({"status": "ok"})

@app.route('/config/<config_uid>/servers/create', methods=['POST'])
@login_required
def create_server(config_uid):
    config = Configuration.query.filter_by(uid=config_uid, user_id=current_user.id).first_or_404()
    alias = request.form['alias']
    url = request.form['url']
    is_default = 'is_default' in request.form

    if is_default:
        
        Server.query.filter_by(config_id=config.id, is_default=True).update({"is_default": False})

    new_server = Server(alias=alias, url=url, config_id=config.id, is_default=is_default)
    db.session.add(new_server)
    db.session.commit()
    flash(_("Server added"), "success")
    return redirect(url_for('edit_config', uid=config_uid, tab="servers"))

@app.route('/config/servers/<int:server_id>/delete')
@login_required
def delete_server(server_id):
    server = Server.query.join(Configuration).filter(
        Server.id == server_id, Configuration.user_id == current_user.id
    ).first_or_404()
    config_uid = server.config.uid
    db.session.delete(server)
    db.session.commit()
    flash(_("Server deleted"), "success")
    return redirect(url_for('edit_config', uid=config_uid, tab="servers"))

@app.route('/config/servers/<int:server_id>/update', methods=['POST'])
@login_required
def update_server(server_id):
    server = Server.query.join(Configuration).filter(
        Server.id == server_id, Configuration.user_id == current_user.id
    ).first_or_404()

    server.alias = request.form['alias']
    server.url = request.form['url']
    server.is_default = 'is_default' in request.form

    if server.is_default:
        
        Server.query.filter_by(config_id=server.config_id, is_default=True).update({"is_default": False})

    db.session.commit()
    flash(_("Server updated"), "success")
    return redirect(url_for('edit_config', uid=server.config.uid, tab="servers"))


# --- Room aliases (per configuration) ---

@app.route('/config/<config_uid>/rooms/create', methods=['POST'])
@login_required
def create_room_alias(config_uid):
    config = Configuration.query.filter_by(uid=config_uid, user_id=current_user.id).first_or_404()
    alias = (request.form.get('alias') or '').strip()
    room_uid = (request.form.get('room_uid') or '').strip()
    if not alias or not room_uid:
        flash('Alias and room are required', 'danger')
        return redirect(url_for('edit_config', uid=config_uid, tab='rooms'))

    # Validate room exists and belongs to user
    room = Room.query.filter_by(uid=room_uid, user_id=current_user.id).first()
    if not room:
        flash('Room not found', 'danger')
        return redirect(url_for('edit_config', uid=config_uid, tab='rooms'))

    # Upsert-ish: if alias exists -> update mapping
    existing = RoomAlias.query.filter_by(config_id=config.id, alias=alias).first()
    if existing:
        existing.room_uid = room_uid
    else:
        db.session.add(RoomAlias(alias=alias, room_uid=room_uid, config_id=config.id))
    db.session.commit()
    flash('Room alias saved', 'success')
    return redirect(url_for('edit_config', uid=config_uid, tab='rooms'))


@app.route('/config/rooms/<int:alias_id>/update', methods=['POST'])
@login_required
def update_room_alias(alias_id):
    ra = RoomAlias.query.join(Configuration).filter(
        RoomAlias.id == alias_id,
        Configuration.user_id == current_user.id
    ).first_or_404()

    alias = (request.form.get('alias') or '').strip()
    room_uid = (request.form.get('room_uid') or '').strip()
    if not alias or not room_uid:
        flash('Alias and room are required', 'danger')
        return redirect(url_for('edit_config', uid=ra.config.uid, tab='rooms'))

    room = Room.query.filter_by(uid=room_uid, user_id=current_user.id).first()
    if not room:
        flash('Room not found', 'danger')
        return redirect(url_for('edit_config', uid=ra.config.uid, tab='rooms'))

    ra.alias = alias
    ra.room_uid = room_uid
    db.session.commit()
    flash('Room alias updated', 'success')
    return redirect(url_for('edit_config', uid=ra.config.uid, tab='rooms'))


@app.route('/config/rooms/<int:alias_id>/delete')
@login_required
def delete_room_alias(alias_id):
    ra = RoomAlias.query.join(Configuration).filter(
        RoomAlias.id == alias_id,
        Configuration.user_id == current_user.id
    ).first_or_404()
    cfg_uid = ra.config.uid
    db.session.delete(ra)
    db.session.commit()
    flash('Room alias deleted', 'success')
    return redirect(url_for('edit_config', uid=cfg_uid, tab='rooms'))

from sqlalchemy.orm import joinedload

def migrate_events_json_to_tables(dry_run=False, commit=True):

    stats = {'classes_scanned':0, 'events_migrated':0, 'actions_migrated':0, 'skipped_existing':0}
    with app.app_context():
        classes = db.session.query(ConfigClass).options(joinedload(ConfigClass.event_objs)).all()
        for cls in classes:
            stats['classes_scanned'] += 1
            events_json = cls.events or []  
            
            if not isinstance(events_json, list) or len(events_json) == 0:
                continue

           
            if cls.event_objs and len(cls.event_objs) > 0:
                stats['skipped_existing'] += 1
                continue

            for ev in events_json:
                
                
                try:
                    if isinstance(ev, str):
                        ev_obj = {'event': ev, 'listener': '', 'source': 'internal', 'server': '', 'method': ''}
                    elif isinstance(ev, dict):
                        ev_obj = ev.copy()
                    else:
                        continue

                    event_name = ev_obj.get('event') or ev_obj.get('event_name') or ''
                    listener = ev_obj.get('listener', '') or ev_obj.get('listener_name','') or ''

                    
                    ce = ClassEvent(event=event_name, listener=listener, class_id=cls.id)
                    if not dry_run:
                        db.session.add(ce)
                        db.session.flush()  

                    
                    
                    actions_list = []
                    if isinstance(ev_obj.get('actions'), list) and len(ev_obj.get('actions'))>0:
                        actions_list = ev_obj.get('actions')
                    else:
                        
                        actions_list = [{
                            'action': 'run',
                            'source': ev_obj.get('source','internal') or 'internal',
                            'server': ev_obj.get('server','') or '',
                            'method': ev_obj.get('method','') or ev_obj.get('method_name','') or '',
                            'postExecuteMethod': ''
                        }]

                    
                    order = 0
                    for a in actions_list:
                        order += 1
                        act = EventAction(
                            action = a.get('action','run'),
                            source = a.get('source','internal') or 'internal',
                            server = a.get('server','') or '',
                            method = a.get('method','') or a.get('method_name','') or '',
                            post_execute_method = a.get('postExecuteMethod','') or a.get('postExecute','') or '',
                            order = order,
                            event_id = ce.id if not dry_run else None
                        )
                        if not dry_run:
                            db.session.add(act)
                        stats['actions_migrated'] += 1

                    stats['events_migrated'] += 1

                except Exception as e:
                    print("Error migrating event for class", cls.id, e)
                    db.session.rollback()
                    continue

        if not dry_run and commit:
            db.session.commit()
    return stats

def get_ws_scheme():
    # If Flask runs behind HTTPS (for example, via nginx with SSL)
    if request.is_secure or request.headers.get('X-Forwarded-Proto', '').lower() == 'https':
        return 'wss'
    return 'ws'


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        print(migrate_events_json_to_tables(dry_run=False))
        try:
            db.create_all(bind='client')
        except Exception as e:
            print('Could not init client bind:', e)


        inspector = db.inspect(db.engine)
        columns = inspector.get_columns('config_class')

        # --- lightweight sqlite migration for new ConfigClass fields (Migration tab) ---
        try:
            col_names = [c.get('name') for c in (columns or [])]
            with db.engine.begin() as conn:
                if 'migration_register_command' not in col_names:
                    conn.execute(text('ALTER TABLE config_class ADD COLUMN migration_register_command BOOLEAN DEFAULT 0'))
                if 'migration_register_on_save' not in col_names:
                    conn.execute(text('ALTER TABLE config_class ADD COLUMN migration_register_on_save BOOLEAN DEFAULT 0'))
                if 'migration_default_room_uid' not in col_names:
                    conn.execute(text('ALTER TABLE config_class ADD COLUMN migration_default_room_uid VARCHAR(36) DEFAULT ""'))
                if 'migration_default_room_alias' not in col_names:
                    conn.execute(text('ALTER TABLE config_class ADD COLUMN migration_default_room_alias VARCHAR(100) DEFAULT ""'))
        except Exception as e:
            print('Could not migrate config_class Migration fields:', e)

         
        if 'config_event' not in inspector.get_table_names():
            db.create_all()
            print("Created config_event table")
        
        if 'config_event_action' not in inspector.get_table_names():
            db.create_all()
            print("Created config_event_action table")
        
        
        if 'config_event' in inspector.get_table_names():
            config_event_columns = [col['name'] for col in inspector.get_columns('config_event')]
            
           
            if 'config_id' not in config_event_columns:
                with db.engine.begin() as conn:
                    conn.execute(text('ALTER TABLE config_event ADD COLUMN config_id INTEGER'))
                    conn.execute(text('CREATE INDEX ix_config_event_config_id ON config_event (config_id)'))
                print("Added config_id to config_event table")
        
        if 'config_event_action' in inspector.get_table_names():
            config_event_action_columns = [col['name'] for col in inspector.get_columns('config_event_action')]
            
            if 'event_id' not in config_event_action_columns:
                with db.engine.begin() as conn:
                    conn.execute(text('ALTER TABLE config_event_action ADD COLUMN event_id INTEGER'))
                    conn.execute(text('CREATE INDEX ix_config_event_action_event_id ON config_event_action (event_id)'))
                print("Added event_id to config_event_action table")

        if 'class_method' in inspector.get_table_names():
            class_method_columns = [col['name'] for col in inspector.get_columns('class_method')]
            
            if 'source' not in class_method_columns:
                with db.engine.begin() as conn:
                    conn.execute(text('ALTER TABLE class_method ADD COLUMN source VARCHAR(100) DEFAULT "internal"'))
                print("Added source column to class_method table")   

            if 'server' not in class_method_columns:
                with db.engine.begin() as conn:
                    conn.execute(text('ALTER TABLE class_method ADD COLUMN server VARCHAR(255) DEFAULT "internal"'))
                print("Added source column to class_method table")         



        if 'room_objects' in inspector.get_table_names():
            room_objects_columns = [col['name'] for col in inspector.get_columns('room_objects')]
        
        if 'acknowledged_by' not in room_objects_columns:
            with db.engine.begin() as conn:
                conn.execute(text('ALTER TABLE room_objects ADD COLUMN acknowledged_by JSON DEFAULT "[]"'))
            print("Added acknowledged_by column to room_objects table")

        if 'config_class' in inspector.get_table_names():
            columns = [col['name'] for col in inspector.get_columns('config_class')]
            
            if 'has_storage' not in columns:
                with db.engine.begin() as conn:
                    conn.execute(text('ALTER TABLE config_class ADD COLUMN has_storage BOOLEAN DEFAULT FALSE'))
            
            if 'class_type' not in columns:
                with db.engine.begin() as conn:
                    conn.execute(text('ALTER TABLE config_class ADD COLUMN class_type VARCHAR(50)'))
            if 'hidden' not in columns:
                with db.engine.begin() as conn:
                    conn.execute(text('ALTER TABLE config_class ADD COLUMN hidden BOOLEAN DEFAULT FALSE'))        
            
            if 'section' not in columns:
                with db.engine.begin() as conn:
                    conn.execute(text('ALTER TABLE config_class ADD COLUMN section VARCHAR(100)'))
            if 'section_code' not in columns:
                with db.engine.begin() as conn:
                    conn.execute(text('ALTER TABLE config_class ADD COLUMN section_code VARCHAR(100)'))     

            if 'display_name' not in columns:
                with db.engine.begin() as conn:
                    conn.execute(text('ALTER TABLE config_class ADD COLUMN display_name VARCHAR(100)'))
            
            if 'cover_image' not in columns:
                with db.engine.begin() as conn:
                    conn.execute(text('ALTER TABLE config_class ADD COLUMN cover_image TEXT'))  
                    
                             
        
        
        if 'config_section' not in inspector.get_table_names():
            section_columns = [col['name'] for col in inspector.get_columns('config_section')]
        
        if 'config_section' in inspector.get_table_names():
            section_columns = [col['name'] for col in inspector.get_columns('config_section')]
            if 'commands' not in section_columns:
                with db.engine.begin() as conn:
                    conn.execute(text('ALTER TABLE config_section ADD COLUMN commands TEXT'))
                
            db.create_all()

        
        if 'user' in inspector.get_table_names():
            user_columns = [col['name'] for col in inspector.get_columns('user')]
            if 'config_display_name' not in user_columns:
                with db.engine.begin() as conn:
                    conn.execute(text('ALTER TABLE user ADD COLUMN config_display_name VARCHAR(100) DEFAULT ""'))

            # Backward compatible defaults: existing users keep access to everything
            if 'can_designer' not in user_columns:
                with db.engine.begin() as conn:
                    conn.execute(text('ALTER TABLE user ADD COLUMN can_designer BOOLEAN DEFAULT TRUE'))
            if 'can_client' not in user_columns:
                with db.engine.begin() as conn:
                    conn.execute(text('ALTER TABLE user ADD COLUMN can_client BOOLEAN DEFAULT TRUE'))
            if 'can_api' not in user_columns:
                with db.engine.begin() as conn:
                    conn.execute(text('ALTER TABLE user ADD COLUMN can_api BOOLEAN DEFAULT TRUE'))
            if 'parent_user_id' not in user_columns:
                with db.engine.begin() as conn:
                    conn.execute(text('ALTER TABLE user ADD COLUMN parent_user_id INTEGER'))

            db.create_all()

        if 'dataset' in inspector.get_table_names():
            dataset_columns = [col['name'] for col in inspector.get_columns('dataset')]
            if 'view_template' not in dataset_columns:
                with db.engine.begin() as conn:
                    conn.execute(text('ALTER TABLE dataset ADD COLUMN view_template TEXT'))
            if 'autoload' not in dataset_columns:
                with db.engine.begin() as conn:
                    conn.execute(text('ALTER TABLE dataset ADD COLUMN autoload BOOLEAN DEFAULT FALSE'))
            db.create_all()  

       
        if 'configuration' in inspector.get_table_names():
            config_columns = [col['name'] for col in inspector.get_columns('configuration')]

            if 'content_uid' not in config_columns:
                with db.engine.begin() as conn:
                    conn.execute(text('ALTER TABLE configuration ADD COLUMN content_uid VARCHAR(100)'))
            if 'vendor' not in config_columns:
                with db.engine.begin() as conn:
                    conn.execute(text('ALTER TABLE configuration ADD COLUMN vendor TEXT'))   

            insp = sa.inspect(db.engine)
            if Configuration.__tablename__ in insp.get_table_names():
                columns = [c["name"] for c in insp.get_columns(Configuration.__tablename__)]
                if "common_layouts" not in columns:
                    print("Migration: add Configuration.common_layouts")
                    with db.engine.begin() as con:
                        con.execute(
                            sa.text(
                                f'ALTER TABLE {Configuration.__tablename__} '
                                'ADD COLUMN common_layouts JSON'
                            )
                        )            

            if 'user_id' not in config_columns:
                with db.engine.begin() as conn:
                    conn.execute(text('ALTER TABLE configuration ADD COLUMN user_id INTEGER'))
                    
                    first_user = db.session.execute(select(User)).scalar()
                    if first_user:
                        conn.execute(text('UPDATE configuration SET user_id = :user_id WHERE user_id IS NULL'), 
                                   {'user_id': first_user.id})
                    
                    conn.execute(text('CREATE INDEX ix_configuration_user_id ON configuration (user_id)'))

            if 'server_name' not in config_columns:
                with db.engine.begin() as conn:
                    conn.execute(text('ALTER TABLE configuration ADD COLUMN server_name VARCHAR(100) DEFAULT ""'))
            
            if 'nodes_server_handlers' not in config_columns:
                with db.engine.begin() as conn:
                    conn.execute(text('ALTER TABLE configuration ADD COLUMN nodes_server_handlers TEXT'))
                    conn.execute(text('ALTER TABLE configuration ADD COLUMN nodes_server_handlers_meta JSON'))        

            
            if 'version' not in config_columns:
                with db.engine.begin() as conn:
                    conn.execute(text('ALTER TABLE configuration ADD COLUMN version VARCHAR(20) DEFAULT "00.00.01"'))
            
            if 'last_modified' not in config_columns:
                with db.engine.begin() as conn:
                    
                    conn.execute(text('ALTER TABLE configuration ADD COLUMN last_modified DATETIME'))
                   
                    conn.execute(text('UPDATE configuration SET last_modified = CURRENT_TIMESTAMP WHERE last_modified IS NULL'))
        
        with app.app_context():
            for cfg in Configuration.query.all():
                if not cfg.content_uid:
                    cfg.content_uid = str(uuid.uuid4())
                if not cfg.vendor:
                    cfg.vendor = cfg.user.config_display_name or cfg.user.email
            db.session.commit()


        if 'config_class' in inspector.get_table_names():
            columns = [col['name'] for col in inspector.get_columns('config_class')]
            
            if 'events' not in columns:
                with db.engine.begin() as conn:
                    conn.execute(text('ALTER TABLE config_class ADD COLUMN events TEXT'))
            if 'display_image_web' not in columns:
                with db.engine.begin() as conn:
                    conn.execute(text('ALTER TABLE config_class ADD COLUMN display_image_web TEXT DEFAULT ""'))

            if 'display_image_table' not in columns:
                with db.engine.begin() as conn:
                    conn.execute(text('ALTER TABLE config_class ADD COLUMN display_image_table TEXT DEFAULT ""'))

            if 'commands' not in columns:
                with db.engine.begin() as conn:
                    conn.execute(text('ALTER TABLE config_class ADD COLUMN commands TEXT DEFAULT ""'))

            if 'use_standard_commands' not in columns:
                with db.engine.begin() as conn:
                    conn.execute(text('ALTER TABLE config_class ADD COLUMN use_standard_commands BOOLEAN DEFAULT TRUE'))

            if 'svg_commands' not in columns:
                with db.engine.begin() as conn:
                    conn.execute(text('ALTER TABLE config_class ADD COLUMN svg_commands TEXT DEFAULT ""'))

            if 'init_screen_layout' not in columns:
                with db.engine.begin() as conn:
                    conn.execute(text('ALTER TABLE config_class ADD COLUMN init_screen_layout TEXT DEFAULT ""'))
               

        if 'configuration' in inspector.get_table_names():
            columns = [col['name'] for col in inspector.get_columns('configuration')]
            if 'nodes_handlers' not in columns:
                with db.engine.begin() as conn:
                    conn.execute(text('ALTER TABLE configuration ADD COLUMN nodes_handlers TEXT'))
                    conn.execute(text('ALTER TABLE configuration ADD COLUMN nodes_handlers_meta JSON'))
        
        
        
    

    # Create a custom WSGI server with WebSocket support
    def application(environ, start_response):
        path = environ.get('PATH_INFO', '')
        
        # Intercept WebSocket requests
        if path == '/ws' and 'wsgi.websocket' in environ:
            ws = environ['wsgi.websocket']
            query_string = environ.get('QUERY_STRING', '')
            parsed_params = parse_qs(query_string)

            channel = parsed_params.get('channel', [''])[0]

            # Node browser channel (separate from Rooms channel)
            if channel == 'nodes':
                handle_nodes_websocket(ws)
                return []

            room_uid = parsed_params.get('room', [''])[0]
            android_id = parsed_params.get('android_id', [''])[0]
            device_model = parsed_params.get('device_model', [''])[0]
            if room_uid:
                handle_websocket(ws, room_uid)
                return []
        
        # All other requests are processed through Flask
        return app(environ, start_response)
    
    server = WSGIServer(
        ('0.0.0.0', 5000),
        application,
        handler_class=WebSocketHandler
    )
    print("Server running on:")
    print("HTTP: http://0.0.0.0:5000")
    print("WebSocket: ws://0.0.0.0:5000/ws?room=ROOM_UID")

    server.serve_forever()#test
