from flask import Flask, render_template_string, request, render_template_string, session, copy_current_request_context, url_for,Markup, render_template, redirect
import json
from flask_socketio import SocketIO,  disconnect
import pathlib
import os

from werkzeug.utils import secure_filename

UPLOAD_FOLDER = 'uploads'

from uiweb import Simple
#from simpleweb import Simple

async_mode = 'threading'
fapp = Flask(__name__,template_folder='templates',static_url_path='',  static_folder='static')

fapp.config['SECRET_KEY'] = 'secret!'
fapp.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
socket_ = SocketIO(fapp,async_mode=async_mode, async_handlers=True)

sid = None

PATH_TO_SETTINGS = 'web_settings.json'
PYTHONPATH=str(pathlib.Path(__file__).parent.absolute())

connected=[]

def get_current_connection(sid):
    l = list(filter(lambda x: x[1] == sid, connected))

    for user in l:
        return user

SW = None
# WebSocket events
@socket_.on('connect_event', namespace='/simpleweb')
def test_message(message):
    global SW
    global connected
    if not SW==None:
        sid = request.sid
        session['sid']=sid
        session['SW']=SW
        session['SW'].set_sid(sid)

        connected.append((socket_, sid, SW))
  

    session['receive_count'] = session.get('receive_count', 0) + 1
 
@socket_.on('run_process', namespace='/simpleweb')
def run_process(message):
    user = get_current_connection(request.sid)
    user[2].run_process(message)

@socket_.on('input_event', namespace='/simpleweb')
def input_event(message):
    user = get_current_connection(request.sid)
    user[2].input_event(message) 

    

@socket_.on('close_maintab', namespace='/simpleweb')
def close_maintab(message):
    user = get_current_connection(request.sid)
    user[2].close_maintab(message)   

@socket_.on('select_tab', namespace='/simpleweb')
def select_tab(message):
    user = get_current_connection(request.sid)
    user[2].select_tab(message) 

@socket_.on('disconnect_request', namespace='/simpleweb')
def disconnect_request():
    global connected
    disconnected = list(filter(lambda x: x[0] == socket_, connected))

    for user in disconnected:
            connected.remove(user)
            print(f'{user[1]} left')
    @copy_current_request_context
    def can_disconnect():
        disconnected = list(filter(lambda x: x[0] == socket_, connected))

        for user in disconnected:
            connected.remove(user)
            print(f'{user[1]} left')

        disconnect()

#Flask events
@fapp.route('/setvalues/', methods=['POST'])
def jscommand(FUNCTION=None):
    session['SW'].set_values(request.json)
    
    return ""

@fapp.route('/setvaluespulse/', methods=['POST'])
def jscommandpulse(FUNCTION=None):
    session['SW'].set_values_pulse(request.json)
     
    return ""    

@fapp.route('/admin', methods=['GET'])
def adminpage():
    if not SW==None:
        
        path = pathlib.Path(PATH_TO_SETTINGS)
        if path.is_file():
            f = open(PATH_TO_SETTINGS)
            settings = json.load(f)
        else:
            settings={"url":"","user":"","password":""}

        return render_template_string(SW.get_admin_html(),settings = settings)

@fapp.route('/uploader', methods = ['PUT', 'POST'])
def upload_file():
   SW.write_settings(request,PATH_TO_SETTINGS)

   return "ok",200



@fapp.route('/upload_file', methods = ['PUT', 'POST'])
def upload_file_ui():
   file = request.files['file'] 
   if file.filename == '':
            #'No selected file'
            return redirect(request.url)
   if file:
            filename = secure_filename(file.filename)
            os.makedirs(PYTHONPATH+os.sep+fapp.config['UPLOAD_FOLDER'],exist_ok=True)
            file.save(PYTHONPATH+os.sep+os.path.join(fapp.config['UPLOAD_FOLDER'], filename))

            user = get_current_connection(request.args.get('sid'))
            user[2].input_event({"data":"upload_file","filename":filename,"source":request.args.get('id')}) 
   

   return "ok",200     

@fapp.route('/static/<path:path>')
def static_file(path):
    return fapp.send_static_file(path)  
 
@fapp.route('/', methods=['GET', 'POST','PUT']) #main page initialization
def index():
    global SW

    SW = Simple(socket_,PYTHONPATH)
    
    SW.load_settings(PATH_TO_SETTINGS)
    
    SW.load_configuration('current_configuration.ui')
   
    res =SW.build_page()
     
    return render_template_string(res)
    
if __name__ == "__main__":
    global_data = {}
 
    socket_.run(fapp, debug=False, host='0.0.0.0', port=1555)