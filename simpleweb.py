import json
import bs4

import uuid
import html
import requests
from requests.auth import HTTPBasicAuth
import sys
import os

import base64



from flask_socketio import emit

import threading
import asyncio
import pathlib
from datetime import datetime
import time





def get_process(configuration,processname):
    for   process in configuration['ClientConfiguration']['Processes']:
      if process.get('ProcessName','')==processname and process.get('type','')=='Process':
        return process

def get_screen(process,screensname=''):
    if len(screensname)==0 and len(process['Operations'])>0:
      return process['Operations'][0]
    else:  
      for   screen in process['Operations']:
        if screen.get('Name','')==screensname and screen.get('type','')=='Operation':
          return screen



def get_decor(elem,additional_styles =None):
  styles = []

  if "TextColor" in elem:
    if len(elem.get("TextColor",""))>0:
      styles.append("color:"+elem.get("TextColor"))

  if "BackgroundColor" in elem:
    if len(elem.get("BackgroundColor",""))>0:
      styles.append("background-color:"+elem.get("BackgroundColor")) 

  if "TextSize" in elem:
    if len(elem.get("TextSize",""))>0:
      styles.append("font-size:"+elem.get("TextSize")+"px")

        

  if "TextBold" in elem:
    if str(elem.get("TextBold",""))=="true" or elem.get("TextBold")==True:
        styles.append("font-weight:bold")

  if "TextItalic" in elem:
    if str(elem.get("TextItalic",""))=="true" or elem.get("TextItalic")==True:
      styles.append("font-style:italic")  
                   
  if "gravity_horizontal" in elem:
    if str(elem.get("gravity_horizontal",""))=="right" :
      styles.append("text-align: right;") 
    elif str(elem.get("gravity_horizontal",""))=="left" :
      styles.append("text-align: left;")
    else:
      styles.append("text-align: center;")
  else:
    styles.append("text-align: center;")    


  if "width" in elem:
                  if str(elem.get("width","")).isnumeric():
                    styles.append("width:"+str(elem.get("width"))+"px")
                  elif  elem.get("width","")=="match_parent":
                    styles.append("width:100%")

  if "height" in elem:
                  if str(elem.get("height","")).isnumeric():
                    styles.append("height:"+str(elem.get("height"))+"px")
                  elif  elem.get("height","")=="match_parent":
                    styles.append("height:100%")   

  styles.append("margin: 3px")                
  if additional_styles!=None:
     for st in additional_styles:
        styles.append(st)

  return  ";".join(styles)          

SOCKET_NAMESPACE='simpleweb'

class Simple:
  

  PYTHONPATH=""
  



  #Socket events

  def close_maintab(self,message):
    for d in self.opened_tabs:
      if d["id"] == message["source"]:
        self.opened_tabs.remove(d)
        break

    if not self.parent_tab_id == None:
      self.socket_.emit('click_button', {"id":"maintab_"+self.parent_tab_id},room=self.sid,namespace='/'+SOCKET_NAMESPACE) 

      current_tab = list(filter(lambda current_tab: current_tab['id'] == self.parent_tab_id, self.opened_tabs))
      if len(current_tab)>0:

        self.current_tab_id = self.parent_tab_id

        #self.hashMap['CurrentTabID'] = self.parent_tab_id
        #self.hashMap['CurrentTabKey'] = current_tab[0].get('key')
        
        #self.hashMap['listener']='MainTabSelect'

        #self.RunEvent("onWEBMainTabSelected",None,True)


    print("Вкладка закрыта:"+str(message))
     

  def select_tab(self,message):
    
    self.select_tab(message)  

  def run_process(self,message):

    self.process_data={}
   
    strprocessname = message.strip()

    if not self.menutemplate ==None:
      menuitem=next((item for item in self.menutemplate if item["caption"] == strprocessname), None)
      if menuitem==None:
        return
      else:
        processname=menuitem.get("process")  
    else:
      processname= strprocessname 

    _cookies = None
    if "_cookies" in self.hashMap:
       _cookies = self.hashMap.get("_cookies")
    self.hashMap = {}
    if _cookies != None:
       self.hashMap["_cookies"] = _cookies

    self.hashMap["base_path"] = Simple.PYTHONPATH

    self.read_globals()

    soup = bs4.BeautifulSoup(features="lxml")
    #tabid = translit(processname, 'ru', reversed=True).replace(" ","_")
    tabid = str(uuid.uuid4().hex)
    self.current_tab_id=tabid

    self.tabsHashMap[self.current_tab_id]=dict(self.hashMap)

    #print(tabid)
    self.added_tables=[]
    
    self.firsttabslayout=[]
    self.screentabs = []

    

    reopen = False
            
    current_tab = list(filter(lambda current_tab: current_tab['key'] == processname, self.opened_tabs))
    if len(current_tab)>0:
      reopen=True
      tabid = current_tab[0]["id"]
      self.current_tab_id = tabid

      self.process = get_process(self.configuration,processname)
      self.screen= get_screen(self.process)

      emit('click_button', {"id":"maintab_"+tabid},room=self.sid,namespace='/'+SOCKET_NAMESPACE)

      self.added_tables=[]
      self.firsttabslayout=[]
      self.screentabs = [] 
      self.RunEvent("onStart")
      layots = self.get_layouts(soup,self.screen,0)
      self.socket_.emit('setvaluehtml', {'key':"root_"+tabid,'value':str(layots),'tabid':tabid},room=self.sid,namespace='/'+SOCKET_NAMESPACE)

      for t in self.added_tables:
        self.socket_.emit('run_datatable', t,room=self.sid,namespace='/'+SOCKET_NAMESPACE) 

      if not "SelectTab" in self.hashMap:
        for t in self.firsttabslayout:
          self.socket_.emit('click_button', {"id":t},room=self.sid,namespace='/'+SOCKET_NAMESPACE) 

      self.RunEvent("onPostStart")

    else:      
      button,tab = self.new_screen_tab(self.configuration,processname,'',soup,tabid)
      emit('add_html', {"id":"maintabs","code":str(button)},room=self.sid,namespace='/'+SOCKET_NAMESPACE)
      emit('add_html', {"id":"maincontainer","code":str(tab)},room=self.sid,namespace='/'+SOCKET_NAMESPACE)     

      self.opened_tabs.append({"id":tabid,"key":processname})
      
                          
        
      emit('click_button', {"id":"maintab_"+tabid},room=self.sid,namespace='/'+SOCKET_NAMESPACE)

    self.new_tabs.append("maintab_"+tabid)

    for t in self.added_tables:
      emit('run_datatable', t,room=self.sid,namespace='/'+SOCKET_NAMESPACE)
    
    for t in self.firsttabslayout:
      emit('click_button', {"id":t},room=self.sid,namespace='/'+SOCKET_NAMESPACE)  
  
    self.RunEvent("onPostStart")

  def set_values(self,jSetValues):
    
    for el in jSetValues:
         for key,value in el.items():
          self.socket_.emit('setvalue', {'key':"d"+self.current_tab_id+"_"+key,'value':el[key],'tabid':self.current_tab_id},room=self.sid,namespace='/'+SOCKET_NAMESPACE)
  def set_values_pulse(self,jSetValues):
    


    for el in jSetValues:
         for key,value in el.items():
          self.socket_.emit('setvaluepulse', {'key':"d"+self.current_tab_id+"_"+key,'value':el[key],'tabid':self.current_tab_id},room=self.sid,namespace='/'+SOCKET_NAMESPACE) 

  def debug(self,breakpoint_data):
    jdata = breakpoint_data  
    t = {
    "type": "table",
    "textsize": "25",
    "hidecaption": "false",
    "editmode": "modal",
    "columns": [
       
        {
        "name": "variable",
        "header": "Переменная",
        "weight": "1",
        "gravity":"left",
        "input":"EditTextText"
        },
        {
        "name": "value",
        "header": "Значение",
        "weight": "1",
        "gravity":"left",
        "input":"EditTextText"
    }

    ]
    }  

    t['rows'] = []
    for k,v in jdata["hashmap"].items():
       t["rows"].append({"variable":k,"value":v})

    self.hashMap["StackTable"] = json.dumps(t,ensure_ascii=False)
    self.hashMap["RefreshScreen"] =""

    self.handle_command()

                 
          
  #def connect_event(self,message):
  #  event = "Connect"

  #  hashMap = self.hashMap
  #  hashMap["event"]=event
  #  self.sid = re

  def get_edit_html(self,jtable,jline,isInsert):
    if 'editlayout' in jtable:
              layout = json.loads(jtable['editlayout'])
    else:  
              layout={
            "type": "LinearLayout",
            "orientation": "vertical",
            "height": "wrap_content",
            "width": "match_parent",
            "weight": "0",
            "Elements": []}

              for column in jtable['columns']:
                if 'input' in column:
                  if column['input']=='EditTextText':  

                    layout["Elements"].append({"type": "LinearLayout",
                    "orientation": "horizontal",
                    "height": "wrap_content",
                    "width": "match_parent",
                    "weight": "0",
                    "Elements": [
                    {
                    "type": "TextView",
                    "Value": column.get("header"),
                    "TextSize": "16",
                    
                    "TextBold": False,
                    "TextItalic": False,
                    "width": "match_parent",
                    "gravity_horizontal": "right",
                    "height": "wrap_content",
                    "weight": 1
                    },{
                    "type": "EditTextText",
                    "Value": "@"+column.get("name"),
                    "Variable": column.get("name"),
                    "TextSize": "16",
                   
                    "TextBold": True,
                    "TextItalic": False,
                    "width": "match_parent",
                    "height": "wrap_content",
                    "gravity_horizontal": "left",
                    "weight": 1
                    }]})  
                  elif column['input']=='EditTextNumeric':  

                    layout["Elements"].append({"type": "LinearLayout",
                    "orientation": "horizontal",
                    "height": "wrap_content",
                    "width": "match_parent",
                    "weight": "0",
                    "Elements": [
                    {
                    "type": "TextView",
                    "Value": column.get("header"),
                    "TextSize": "16",
                    
                    "TextBold": False,
                    "TextItalic": False,
                    "width": "match_parent",
                    "height": "wrap_content",
                    "gravity_horizontal": "right",
                    "weight": 1
                    },{
                    "type": "EditTextNumeric",
                    "Value": "@"+column.get("name"),
                    "Variable": column.get("name"),
                    "TextSize": "16",
                    
                    "TextBold": True,
                    "TextItalic": False,
                    "width": "match_parent",
                    "height": "wrap_content",
                    "gravity_horizontal": "left",
                    "weight": 1
                    }]})    
                  elif column['input']=='EditTextPass':  

                    layout["Elements"].append({"type": "LinearLayout",
                    "orientation": "horizontal",
                    "height": "wrap_content",
                    "width": "match_parent",
                    "weight": "0",
                    "Elements": [
                    {
                    "type": "TextView",
                    "Value": column.get("header"),
                    "TextSize": "16",
                    
                    "TextBold": False,
                    "TextItalic": False,
                    "width": "match_parent",
                    "height": "wrap_content",
                    "gravity_horizontal": "right",
                    "weight": 1
                    },{
                    "type": "EditTextPass",
                    "Value": "@"+column.get("name"),
                    "Variable": column.get("name"),
                    "TextSize": "16",
                    
                    "TextBold": True,
                    "TextItalic": False,
                    "width": "match_parent",
                    "height": "wrap_content",
                    "gravity_horizontal": "left",
                    "weight": 1
                    }]})  
                  elif column['input']=='MultilineText':  

                    layout["Elements"].append({"type": "LinearLayout",
                    "orientation": "vertical",
                    "height": "wrap_content",
                    "width": "match_parent",
                    "weight": "0",
                    "Elements": [
                    {
                    "type": "TextView",
                    "Value": column.get("header"),
                    "TextSize": "16",
                   
                    "TextBold": False,
                    "TextItalic": False,
                    "width": "match_parent",
                    "height": "wrap_content",
                    "weight": 1
                    },{
                    "type": "MultilineText",
                    "Value": "@"+column.get("name"),
                    "Variable": column.get("name"),
                    "TextSize": "16",
                   
                    "TextBold": True,
                    "TextItalic": False,
                    "width": "match_parent",
                    "height": "wrap_content",
                    "weight": 1
                    }]})
                  elif column['input']=='CheckBox':  

                    layout["Elements"].append({"type": "LinearLayout",
                    "orientation": "horizontal",
                    "height": "wrap_content",
                    "width": "match_parent",
                    "weight": "0",
                    "Elements": [
                    {
                    "type": "CheckBox",
                    "Value": "@"+column.get("name"),
                    "Variable": column.get("name"),
                    "TextSize": "16",
                   
                    "TextBold": True,
                    "TextItalic": False,
                    "width": "wrap_content",
                    "height": "wrap_content",
                    "gravity_horizontal": "right",
                    "weight": 1
                    },{
                    "type": "TextView",
                    "Value": column.get("header"),
                    "TextSize": "16",
                    
                    "TextBold": False,
                    "TextItalic": False,
                    "width": "match_parent",
                    "height": "wrap_content",
                    "gravity_horizontal": "left",
                    "weight": 1
                    }]})         
                else:
                  if not isInsert:  

                   layout["Elements"].append({"type": "LinearLayout",
                  "orientation": "horizontal",
                  "height": "wrap_content",
                  "width": "match_parent",
                  "weight": "0",
                  "Elements": [
                  {
                  "type": "TextView",
                  "Value": column.get("header"),
                  "TextSize": "16",
                  
                  "TextBold": False,
                  "TextItalic": False,
                  "width": "match_parent",
                  "height": "wrap_content",
                  "gravity_horizontal": "right",
                  "weight": 1
                  },{
                  "type": "TextView",
                  "Value":"@"+ column.get("name"),
                  "TextSize": "16",
                 
                  "TextBold": True,
                  "TextItalic": False,
                  "width": "match_parent",
                  "height": "wrap_content",
                  "gravity_horizontal": "left",
                  "weight": 1
                  }]})  
            



            

              
              
              YesBtn = "Сохранить"
              NoBtn = "Отмена"
              title = "Редактирование записи"
              
              soup = bs4.BeautifulSoup(features="lxml")
              modalhtml=html.unescape(str(self.get_layouts(soup,layout,0,"modal_",jline)))

              dialogHTML = """<dialog>
              <div class="dialogmodal-header">
        
                <h4>"""+title+"""</h4>
              </div>
              <p/>
              <div id=contentModal>   """+ modalhtml + """    </div>
              <p/>
              <div>
              <button class="closedialog" id="onResultPositive">"""            +YesBtn+            """</button>

              <button class="closedialog" id="onResultNegative">"""            +NoBtn+            """</button>
              </div>
              </dialog>"""
                
    return dialogHTML
        
  def js_result(self,message):

    if message['id'] in self.js_results_async:


      postExecute = self.js_results_async[message['id']][0]
      tab_id = self.js_results_async[message['id']][1]
      
      

      self.js_results_async.pop( message['id'], None)

      if message.get("code")==1:
        jHashMap = message["value"]
        for key, value in jHashMap.items():
            self.hashMap[key]=value

        self.handle_command(tab_id)

        if postExecute!=None and postExecute!='':
          self.RunEvent(None,postExecute)

      else:
        self.hashMap['ErrorMessage']= message.get("value")
        self.socket_.emit('error', {'code':str(message.get("value"))},room=self.sid,namespace='/'+SOCKET_NAMESPACE)

      
    else:
      self.js_results[message['id']] = message
    


  def input_event(self,message):
  
    event = "Input"

    hashMap = self.hashMap
    hashMap["event"]=event

    if not message==None:     
        if message.get('data')=='tab_click':
           source = message.get('source')
           #print(source)
           hashMap["current_tab_id"] =  source
           return   
        elif message.get('data')=='barcode':
          barcodeelements = list(filter(lambda tag: tag['type'] == "barcode", self.screen['Elements']))
          if len(barcodeelements)>0:
            hashMap['listener']='barcode'
            hashMap[barcodeelements[0]['Variable']]=message['barcode']

          else:
            return  

        elif message.get('data')=='upload_file':
          
          spl = message.get('source').split('_')
          hashMap["file_id"]=spl[1]
          hashMap["filename"]=message.get('filename')
          hashMap['listener']='upload_file'

        elif message.get('data')=='canvas_mouse_event':
          hashMap['listener']='canvas_mouse_event'
          lid = message.get('source').split('_')
          hashMap[lid[1]] = message.get('values')
          
          spl = message.get('source').split('_')

        elif message.get('data')=='get_cookie': 
           mCookie = message.get('value')
           hashMap['_cookies']=mCookie

        elif message.get('data')=='table_click' and not message.get('source')==None:
          hashMap["listener"]='TableClick'
          spl = message.get('source').split('_')
          hashMap["table_id"]=message.get('source')[message.get('source').find(spl[2])+len(spl[2])+1:]
          hashMap["selected_line_id"]=spl[1]

          hashMap["selected_line_"+hashMap["table_id"]]=spl[1]

          
        
        elif message.get('data')=='table_doubleclick' and not message.get('source')==None:
          hashMap["listener"]='TableDoubleClick'
          spl = message.get('source').split('_')
          hashMap["table_id"]=message.get('source')[message.get('source').find(spl[2])+len(spl[2])+1:]
          hashMap["selected_line_id"]=spl[1]
          
          if self.hashMap.get(spl[3])!=None:
            jtable =json.loads(self.hashMap.get(spl[3]))
            if jtable.get('editmode')=='modal':

              jline = jtable['rows'][int(spl[1])]

              dialogHTML = self.get_edit_html(jtable,jline,False)

              self.socket_.emit('setvaluehtml', {"key":"modaldialog","value":dialogHTML},room=self.sid,namespace='/'+SOCKET_NAMESPACE)
              self.socket_.emit('show_modal', {'table_id':hashMap["table_id"],'selected_line_id':hashMap["selected_line_id"]},room=self.sid,namespace='/'+SOCKET_NAMESPACE)
        elif message.get('data')=='select_input':
           hashMap[message['source'][34:]]=message.get('value')
           hashMap['listener'] = message['source'][34:]
        elif message.get('data')=='edittable_result':
          if message.get("source")=='onResultPositive':
            tableid = message.get('table_id')
            selected_line_id = message.get('selected_line_id',"-1")
            jtable = json.loads(hashMap.get(tableid))
            jvalues = json.loads(message.get('values'))

            lvalues={}

            if selected_line_id=="-1":
              jrow = {}
              for item in jvalues:
                  for key,value in item.items():
                    skey = key.split('_')
                    jrow[skey[2]]=value
                    lvalues[skey[2]]=value
              jtable['rows'].append(jrow)     
            else:  
              jrow = jtable['rows'][int(selected_line_id)]
            
              
              for item in jvalues:
                  for key,value in item.items():
                    skey = key.split('_')
                    jrow[skey[2]]=value
                    lvalues[skey[2]]=value

            hashMap["listener"]='TableEditModal'
           
            hashMap["table_id"]=tableid
            hashMap["selected_line_id"]=selected_line_id
           
            hashMap["table_values"]=json.dumps(lvalues,ensure_ascii=False)
           
            hashMap["selected_line"]=json.dumps(jrow,ensure_ascii=False)  

            hashMap[tableid]=json.dumps(jtable,ensure_ascii=False) 
            hashMap['SetValuesTable']=json.dumps([{tableid:jtable}])     
          else:
            hashMap["listener"]=''


        elif message.get('data')=='table_edit' and not message.get('source_row')==None:
          hashMap["listener"]='TableEdit'
          spl = message.get('source_row').split('_')
          hashMap["table_id"]=spl[3]
          hashMap["selected_line_id"]=spl[1]
          if len(message.get("valuetext",''))>0 :
            hashMap["table_value"]=str(message.get("valuetext",''))
          else: #пока чекбокс
            hashMap["table_value"]=str(message.get("valuecb")).lower()
          if len(spl[3])>0:
            table = json.loads(hashMap.get(spl[3]))  
            columns = table['columns']
            hashMap["table_column"]=columns[message.get('source_column')]['name']
            rows = table['rows']
            hashMap["selected_line"]=json.dumps(rows[int(spl[1])],ensure_ascii=False)

        elif message.get('data')=='card_event':
          hashMap["listener"]='LayoutAction'
          spl = message.get('source').split('_')
          hashMap["card_id"]=str(spl[3])
          hashMap["selected_card_position"]=spl[1]  
          
          elemid=""
          for i in range(5, len(spl)):
            sep=""
            if len(elemid)>0:
              sep="_"
            elemid+=sep+spl[i]

          hashMap["layout_listener"]=elemid
          self.blocknext=True
        elif message.get('data')=='clipboard_result':  
          hashMap["event"]='clipboard'
          hashMap["listener"]='clipboard_result'
          hashMap["clipboard_result"]=message.get('value')
        elif message.get('data')=='dialog_result':  
          hashMap["event"]=message.get('source')
          on_change=False
          if message.get('source')=='onResultPositive' or message.get('source')=='onResultNegative':
            hashMap["listener"]=message.get('source')
          else:  
            on_change=True
            

            #hashMap["listener"]=message.get('source') 

          jvalues = json.loads(message.get('values'))
          jresvalues = []
          for dval in jvalues:
             for key,value in dval.items():
              if key == 'base64':
                tempj = {}
                tempj[key] =value
                jresvalues.append(tempj)
              else:
                tempj = {}
                if self.current_tab_id in key:
                  tempj[key[34:]] =value
                  if on_change:
                     hashMap[key[34:]] =value
                else:  
                  tempj[key] =value 
                  if on_change:
                     hashMap[key] =value
                
                jresvalues.append(tempj)
             
          if on_change:
            if self.current_tab_id in message.get("source"):
                hashMap["listener"] = message.get("source")[34:]
            else:  
                hashMap["listener"] =message.get("source")
             
          hashMap["dialog_values"]=json.dumps(jresvalues,ensure_ascii=False)
        elif message.get('data')=='card_click':
          if self.blocknext:
            self.blocknext=False
            return  
          else:  
            hashMap["listener"]='CardsClick'
            spl = message.get('source').split('_')
            hashMap["card_id"]=str(spl[3])
            hashMap["selected_card_position"]=spl[1]  
        elif message.get('data')=='text_input': 
             if self.current_tab_id in message.get('source'):
                        hashMap[message.get('source')[34:]] =message.get('value')

             hashMap["listener"]=message['source'][34:]
             
             if "#" in message['source']:
               hashMap["listener"]=message['source'][1:]
        else:     
          if 'values' in message:
              jvalues = json.loads(message['values'])
              for el in jvalues:
                  for key,value in el.items():
                    if self.current_tab_id in key:
                        hashMap[key[34:]] =el[key]
                    else:  
                        hashMap[key] =value    
          
          if 'source' in message:

            hashMap["listener"]=message['source'][34:]

            if "#" in message['source']:
               hashMap["listener"]=message['source'][1:]
               
        
        #json_str = {"client":"1","process":"тест","operation":"новый экран","hashmap":hashMap}

        #response  = None

        #operation = Simple.screen.get('DefOnInput','')

        try:
          if "JSOutput" in message:
             hashMap["JSOutput"] = message("JSOutput")
        except:
           pass     

        self.RunEvent("onInput")

        #Python
        #if len(operation)>0:
        #  response = self.set_input(operation,json.dumps(json_str).encode('utf-8'),process_data)
        #jresponse = json.loads(response)
        #hashMap.clear()
        
           

        #if "hashmap" in jresponse:   
                #jHashMap = jresponse["hashmap"]
                #for valpair in jHashMap:
                    #hashMap.append({"key":valpair['key'],"value":valpair['value']})
              

        
              #emit('reload', {}) 
             #                

  def handle_command(self,current_tab=None):

    

    if current_tab==None:
      active_tab = self.current_tab_id
    else:
      active_tab = current_tab

    need_run_on_start = False

    #Simple.socket_.emit('setvaluepulse', {'key':"d"+Simple.current_tab_id+"_"+key,'value':el[key],'tabid':Simple.current_tab_id},sid=self.sid,namespace='/'+SOCKET_NAMESPACE) 
    if  'SetCookie' in self.hashMap:
          
          jSetValues = json.loads(self.hashMap.get('SetCookie'))
          for item in jSetValues:
             if not "expires" in item:
                item["expires"]=1
          
          self.socket_.emit('setcookie', jSetValues,room=self.sid,namespace='/'+SOCKET_NAMESPACE) 
                     #print("d"+Simple.current_tab_id+"_"+key)
                     
          self.hashMap.pop('SetCookie',None)
    if  'GetCookies' in self.hashMap:
          self.hashMap.pop('GetCookies',None)  
           
          self.socket_.emit('getcookie', {},room=self.sid,namespace='/'+SOCKET_NAMESPACE) 
                     #print("d"+Simple.current_tab_id+"_"+key)
                     
              
    if  'SetValues' in self.hashMap:
          #TODO переделать одним запросом
          jSetValues = json.loads(self.hashMap.get('SetValues'))
          for el in jSetValues:
              for key,value in el.items():
                     self.socket_.emit('setvalue', {'key':"d"+self.current_tab_id+"_"+key,'value':html.unescape(el[key]),'tabid':self.current_tab_id},room=self.sid,namespace='/'+SOCKET_NAMESPACE) 
                     #print("d"+Simple.current_tab_id+"_"+key)
                     
          self.hashMap.pop('SetValues',None)
    if  'SetValuesEdit' in self.hashMap:
          #TODO переделать одним запросом
          jSetValues = json.loads(self.hashMap.get('SetValuesEdit'))
          for el in jSetValues:
              for key,value in el.items():
                     self.socket_.emit('setvalueedit', {'key':"d"+self.current_tab_id+"_"+key,'value':html.unescape(el[key]),'tabid':self.current_tab_id},room=self.sid,namespace='/'+SOCKET_NAMESPACE) 
                     #print("d"+Simple.current_tab_id+"_"+key)
                     
          self.hashMap.pop('SetValuesEdit',None)     

        
    if  'InitCanvas' in self.hashMap:
         
          jSetValues = json.loads(self.hashMap.get('InitCanvas'))
          for key,value in jSetValues.items():
            self.socket_.emit('initcanvas', {'key':"d"+self.current_tab_id+"_"+key,'value':html.unescape(jSetValues[key]),'tabid':self.current_tab_id},room=self.sid,namespace='/'+SOCKET_NAMESPACE) 
                      
          self.hashMap.pop('InitCanvas',None)  
    
    if  'SetCanvas' in self.hashMap:
         
          jSetValues = json.loads(self.hashMap.get('SetCanvas'))
          for key,value in jSetValues.items():
            self.socket_.emit('setcanvas', {'key':"d"+self.current_tab_id+"_"+key,'value':html.unescape(jSetValues[key]),'tabid':self.current_tab_id},room=self.sid,namespace='/'+SOCKET_NAMESPACE) 
                      
          self.hashMap.pop('SetCanvas',None)  
    if  'StopCanvasEvents' in self.hashMap:
         
          self.socket_.emit('stopeventscanvas', {'key':"d"+self.current_tab_id+"_StopEvents",'value':'','tabid':self.current_tab_id},room=self.sid,namespace='/'+SOCKET_NAMESPACE) 
                      
          self.hashMap.pop('StopCanvasEvents',None) 
    
    if  'StartCanvasEvents' in self.hashMap:
         
          self.socket_.emit('starteventscanvas', {'key':"d"+self.current_tab_id+"_StartEvents",'value':'','tabid':self.current_tab_id},room=self.sid,namespace='/'+SOCKET_NAMESPACE) 
                      
          self.hashMap.pop('StartCanvasEvents',None)              

    if  'StackToFront' in self.hashMap:
          self.hashMap.pop('StackToFront',None)         

          jSetValues = self.hashMap
          self.socket_.emit('initstack', {'values':jSetValues,'tabid':self.current_tab_id},room=self.sid,namespace='/'+SOCKET_NAMESPACE) 
                      
                    

    if  'SetValuesPulse' in self.hashMap:
          #TODO переделать одним запросом
          jSetValues = json.loads(self.hashMap.get('SetValuesPulse'))

          #r = requests.post('http://localhost:5000/setvaluespulse', json=jSetValues)

          #self.set_values_pulse(jSetValues)
          for el in jSetValues:
              for key,value in el.items():
                     self.socket_.emit('setvaluepulse', {'key':"d"+active_tab+"_"+key,'value':html.unescape(el[key]),'tabid':active_tab},room=self.sid,namespace='/'+SOCKET_NAMESPACE) 
                     #jSetValues = [{'key':"d"+Simple.current_tab_id+"_"+key,'value':el[key],'tabid':Simple.current_tab_id}]
                     #self.set_values_pulse(jSetValues)
          self.hashMap.pop('SetValuesPulse',None)  

    if  'SetValuesTable' in self.hashMap:
          
          jSetValues = json.loads(self.hashMap.get('SetValuesTable'))
          for el in jSetValues:
              for key,value in el.items():
                     self.socket_.emit('setvaluehtml', {'key':"tablediv_"+"d"+self.current_tab_id+"_"+key,'value':str(self.add_table(json.dumps(el[key],ensure_ascii=False),"d"+self.current_tab_id+"_"+key)),'tabid':self.current_tab_id},sid=self.sid,namespace='/'+SOCKET_NAMESPACE) 
                     #self.socket_.emit('run_datatable',{"id":"d"+self.current_tab_id+"_"+key} ,room=self.sid,namespace='/'+SOCKET_NAMESPACE)
          self.hashMap.pop('SetValuesTable',None)  
    if  'SetValuesHTML' in self.hashMap:
          
          jSetValues = json.loads(self.hashMap.get('SetValuesHTML'))
          for el in jSetValues:
              for key,value in el.items():
                     self.socket_.emit('setvaluehtml', {'key':"d"+self.current_tab_id+"_"+key,'value':str(el[key]),'tabid':self.current_tab_id},sid=self.sid,namespace='/'+SOCKET_NAMESPACE) 
                     
          self.hashMap.pop('SetValuesTable',None)        
    if  'SetValuesCards' in self.hashMap:
          #TODO переделать одним запросом
          jSetValues = json.loads(self.hashMap.get('SetValuesCards'))
          for el in jSetValues:
              for key,value in el.items():
                     self.socket_.emit('setvaluehtml', {'key':"cardsdiv_"+"d"+self.current_tab_id+"_"+key,'value':str(self.add_cards(json.dumps(el[key],ensure_ascii=False),"d"+self.current_tab_id+"_"+key)),'tabid':self.current_tab_id},sid=self.sid,namespace='/'+SOCKET_NAMESPACE) 
          self.hashMap.pop('SetValuesCards',None)        



             

    if  'LoginCommit' in self.hashMap:
          self.isreload=True
          #self.socket_.emit('reload', {},sid=self.sid,namespace='/'+SOCKET_NAMESPACE) 
          
          #self.socket_.emit('close_tab', {'buttonid':"maintab_"+self.current_tab_id,'tabid':self.current_tab_id},sid=self.sid,namespace='/'+SOCKET_NAMESPACE)
          soup = bs4.BeautifulSoup(features="lxml")

          menustr=self.configuration['ClientConfiguration'].get("MenuWebTemplate")  
          self.make_menu(soup,soup,menustr)

          self.socket_.emit('setvaluehtml', {"key":"sidenav","value":str(soup)},room=self.sid,namespace='/'+SOCKET_NAMESPACE)
          self.socket_.emit('setmenulisteners', {},room=self.sid,namespace='/'+SOCKET_NAMESPACE)

          


          self.hashMap.pop('LoginCommit',None)              

    
    if 'OpenScreen' in self.hashMap:

            self.parent_tab_id = self.current_tab_id

            tabparameters = json.loads(self.hashMap.get('OpenScreen'))
            self.hashMap.pop('OpenScreen',None)    
            soup = bs4.BeautifulSoup(features="lxml")
            tabid = str(uuid.uuid4().hex)
            self.current_tab_id=tabid
            self.added_tables=[]
            self.firsttabslayout=[]
            self.screentabs = []

            title=None
            if 'SetTitle' in self.hashMap:
              title = self.hashMap.get('SetTitle','')
              self.hashMap.pop('SetTitle',None)   

            self.tabsHashMap[active_tab]=dict(self.hashMap)

            # if "key" in tabparameters:
            #    tabid = tabparameters["key"]
            #    self.current_tab_id = tabid

            reopen = False
            if "reopen" in tabparameters and "key" in tabparameters:
               current_tab = list(filter(lambda current_tab: current_tab['key'] == tabparameters['key'], self.opened_tabs))
               if len(current_tab)>0:
                  reopen=True
                  tabid = current_tab[0]["id"]
                  self.current_tab_id = tabid
               
            noclose=False   
            if "no_close" in tabparameters:
              noclose = tabparameters.get("no_close",False) 

            self.modal=""   
            if tabparameters.get("modal")==True:
              self.modal = self.current_tab_id   
                  
            if not reopen:
              button,tab = self.new_screen_tab(self.configuration,tabparameters['process'],tabparameters['screen'],soup,tabid,title,noclose)
              self.socket_.emit('add_html', {"id":"maintabs","code":str(button)},room=self.sid,namespace='/'+SOCKET_NAMESPACE)
              self.socket_.emit('add_html', {"id":"maincontainer","code":str(tab)},room=self.sid,namespace='/'+SOCKET_NAMESPACE) 
              
              self.opened_tabs.append({"id":tabid,"key":tabparameters.get("key")})

              self.RunEvent("onPostStart")  
            else:
               
              self.process = get_process(self.configuration,tabparameters['process'])
              self.screen= get_screen(self.process,tabparameters['screen'])

              need_run_on_start=True

            
            self.socket_.emit('click_button', {"id":"maintab_"+tabid},room=self.sid,namespace='/'+SOCKET_NAMESPACE)
            self.new_tabs.append("maintab_"+tabid)

            

            
            for t in self.added_tables:
              self.socket_.emit('run_datatable', t,room=self.sid,namespace='/'+SOCKET_NAMESPACE)

            for t in self.firsttabslayout:
              self.socket_.emit('click_button', {"id":t},room=self.sid,namespace='/'+SOCKET_NAMESPACE)
           
            if not reopen:
              if not self.parent_tab_id == None:
                
                self.current_tab_id=self.parent_tab_id

             

    if 'RefreshScreen' in self.hashMap:
          self.hashMap.pop('RefreshScreen',None) 
          
          soup = bs4.BeautifulSoup(features="lxml")
          
          self.added_tables=[]
          self.firsttabslayout=[]
          self.screentabs = []

          self.RunEvent("onStart")
          layots = self.get_layouts(soup,self.screen,0)
          self.socket_.emit('setvaluehtml', {'key':"root_"+self.current_tab_id,'value':str(layots),'tabid':self.current_tab_id},room=self.sid,namespace='/'+SOCKET_NAMESPACE)

          for t in self.added_tables:
              self.socket_.emit('run_datatable', t,room=self.sid,namespace='/'+SOCKET_NAMESPACE) 

          if not "SelectTab" in self.hashMap:
            for t in self.firsttabslayout:
              self.socket_.emit('click_button', {"id":t},room=self.sid,namespace='/'+SOCKET_NAMESPACE)          

          self.RunEvent("onPostStart") 

    if 'SelectTab' in self.hashMap:
          tab_name = self.hashMap.get("SelectTab")
          self.hashMap.pop('SelectTab',None) 

          for t in self.screentabs:
            if tab_name in t:
              self.socket_.emit('click_button', {"id":t},room=self.sid,namespace='/'+SOCKET_NAMESPACE)          
              break

          

    ct = self.hashMap.get('CloseTab')
    if  'CloseTab' in self.hashMap:
          
          
            closeid = self.current_tab_id
            
            no_click=False
            if ct!=None:
              if len(ct)>0:
                current_tab = list(filter(lambda current_tab: current_tab['key'] == ct, self.opened_tabs))
                if len(current_tab)>0:
                      no_click=True
                      reopen=True
                      closeid = current_tab[0]["id"]
              
          
            self.socket_.emit('close_tab', {'buttonid':"maintab_"+closeid,'tabid':closeid},room=self.sid,namespace='/'+SOCKET_NAMESPACE) 
            self.hashMap.pop('CloseTab',None)   

            for d in self.opened_tabs:
              if d["id"] == closeid:
                self.opened_tabs.remove(d)
                break

            if not no_click:
              if not self.parent_tab_id == None:
                self.socket_.emit('click_button', {"id":"maintab_"+self.parent_tab_id},room=self.sid,namespace='/'+SOCKET_NAMESPACE)
                
                self.current_tab_id=self.parent_tab_id

    if 'BlockTabs' in self.hashMap:
       self.socket_.emit('blocktabs', {},room=self.sid,namespace='/'+SOCKET_NAMESPACE) 
       self.hashMap.pop('BlockTabs',None)

    if 'UnblockTabs' in self.hashMap:
       self.socket_.emit('unblocktabs', {},room=self.sid,namespace='/'+SOCKET_NAMESPACE) 
       self.hashMap.pop('UnblockTabs',None)   

    if 'TableAddRow' in self.hashMap:
      table_id = self.hashMap.get('TableAddRow')
      jtable =json.loads(self.hashMap.get(table_id))
      self.hashMap.pop('TableAddRow',None)    
      
      if jtable.get('editmode')=='modal':

            jline = {}

            dialogHTML = self.get_edit_html(jtable,jline,True)

            self.socket_.emit('setvaluehtml', {"key":"modaldialog","value":dialogHTML},room=self.sid,namespace='/'+SOCKET_NAMESPACE)
            self.socket_.emit('show_modal', {'table_id':table_id,'selected_line_id':'-1'},room=self.sid,namespace='/'+SOCKET_NAMESPACE)            

   
    if 'TableEditRow' in self.hashMap:
      table_id = self.hashMap.get('TableEditRow')
      jtable =json.loads(self.hashMap.get(table_id))
      self.hashMap.pop('TableEditRow',None)    
      
      if jtable.get('editmode')=='modal':

            sel_line = 'selected_line_'+table_id
            if sel_line in self.hashMap:
     
              jline = jtable['rows'][int(int(self.hashMap.get(sel_line)))]

              dialogHTML = self.get_edit_html(jtable,jline,False)

              self.socket_.emit('setvaluehtml', {"key":"modaldialog","value":dialogHTML},room=self.sid,namespace='/'+SOCKET_NAMESPACE)
              self.socket_.emit('show_modal', {'table_id':self.hashMap["table_id"],'selected_line_id':self.hashMap["selected_line_id"]},room=self.sid,namespace='/'+SOCKET_NAMESPACE)  
    

       
    if 'UploadFile' in self.hashMap:
      file_id = self.hashMap.get('UploadFile')
      
      self.hashMap.pop('UploadFile',None)    
      
      self.socket_.emit('upload_file', {'file_id':"d"+self.current_tab_id+"_"+file_id, "sid":self.sid},room=self.sid,namespace='/'+SOCKET_NAMESPACE) 

    if 'DownloadFile' in self.hashMap:
      filename = self.hashMap.get('DownloadFile')
      self.hashMap.pop('DownloadFile',None) 

      self.socket_.emit('download_file', {'filename':filename},room=self.sid,namespace='/'+SOCKET_NAMESPACE)


    if 'toast' in self.hashMap:
            text = self.hashMap.get('toast','')
            self.hashMap.pop('toast',None) 
            toastid = str(uuid.uuid4().hex)
           # toasthtml = """<div class="alert" id="""+toastid+"""
  #<span class="closebtn" onclick="this.parentElement.style.display='none';">&times;</span> """ + text+ '</div>'
            self.socket_.emit('toast', {'code':text,'id':toastid},room=self.sid,namespace='/'+SOCKET_NAMESPACE) 

    if 'beep' in self.hashMap:
            
            self.hashMap.pop('beep',None) 
            toastid = str(uuid.uuid4().hex)
           
            self.socket_.emit('beep', {},room=self.sid,namespace='/'+SOCKET_NAMESPACE,to=self.sid)          

    if 'ShowDialog' in self.hashMap:
            text = self.hashMap.get('ShowDialog','')
            self.hashMap.pop('ShowDialog',None) 
            title="Вопрос"
            YesBtn = 'Да'
            NoBtn = 'Нет'
            if 'ShowDialogStyle' in self.hashMap:
              strstyle = self.hashMap.get('ShowDialogStyle')

              try:
                jstyle = json.loads(strstyle)
                YesBtn = jstyle.get("yes","")
                NoBtn = jstyle.get("no","")
                title = jstyle.get("title","")
              except ValueError as e:  
                self.hashMap.put("ErrorMessage",str(e))

              self.hashMap.pop('ShowDialogStyle',None) 

            toastid = str(uuid.uuid4().hex)

            if "ShowDialogLayout" in self.hashMap:
             soup = bs4.BeautifulSoup(features="lxml")
             dialog_layout = json.loads(self.hashMap.get("ShowDialogLayout"))
             
             self.hashMap.pop('ShowDialogLayout',None) 
             
             layoutHTML = str(self.get_layouts(soup,dialog_layout,0))

             if  "ShowDialogActive" in self.hashMap:
                ids_to_search = str(self.hashMap.get("ShowDialogActive")).split(";")
                for id_to_search in ids_to_search:
                  
                  layoutHTML = layoutHTML.replace(id_to_search+'" ',id_to_search+'"' +'class="closedialogchange"' +' ' )

             dialogHTML = """<dialog style="overflow:auto;resize:both;min-height:10px;">
              <div class="dialogmodal-header" >
        
                <h4>"""+title+"""</h4>
              </div>
              <p/>
              <div id=contentModalDialog>   """+ layoutHTML + """    </div>
              <p/>
              <div>
              <button class="closedialog" id="onResultPositive">"""            +YesBtn+            """</button>

              <button class="closedialog" id="onResultNegative">"""            +NoBtn+            """</button>
              </div>
              </dialog>"""  
            
            else:
              dialogHTML = """<dialog>
              <div class="dialogmodal-header">
        
                <h4>"""+title+"""</h4>
              </div>
              <p/>
              <div>   """+ text + """    </div>
              <p/>
              <div>
              <button class="closedialog" id="onResultPositive">"""            +YesBtn+            """</button>

              <button class="closedialog" id="onResultNegative">"""            +NoBtn+            """</button>
              </div>
              </dialog>"""
            self.socket_.emit('setvaluehtml', {"key":"modaldialog","value":dialogHTML},room=self.sid,namespace='/'+SOCKET_NAMESPACE)
            self.socket_.emit('show_dialog', {'code':text,'id':toastid},room=self.sid,namespace='/'+SOCKET_NAMESPACE)  

    if 'basic_notification' in self.hashMap:
            jnotification = json.loads(self.hashMap.get("basic_notification"))
            self.hashMap.pop('basic_notification',None) 

            text = jnotification.get('message','')
            notificationid = str(jnotification.get('number',''))
            title = jnotification.get('title','')

            self.socket_.emit('notification', {'text':text,'id':notificationid,'title':title},room=self.sid,namespace='/'+SOCKET_NAMESPACE) 

    if 'ReadClipboard' in self.hashMap:
            
            self.hashMap.pop('ReadClipboard',None) 

            self.socket_.emit('read_clipboard', {"type":"text"},room=self.sid,namespace='/'+SOCKET_NAMESPACE)   

    if 'WriteClipboard' in self.hashMap:
            value = self.hashMap.get("WriteClipboard")
            
            self.hashMap.pop('WriteClipboard',None) 

            self.socket_.emit('write_clipboard', {"value":value},room=self.sid,namespace='/'+SOCKET_NAMESPACE)                     

    if 'ShowScreen' in self.hashMap:
            screenname = self.hashMap.get('ShowScreen','')
            if "{" in screenname and "}" in screenname and ":" in screenname: #looks like json...
              jdata = json.loads(screenname)
              process = get_process(self.configuration,jdata['process'])
              screen=get_screen(process,jdata['screen'])
            else:  
              screen= get_screen(self.process,screenname)

            if screen==None:
              self.socket_.emit('setvaluehtml', {'key':"root_"+self.current_tab_id,'value':'<h1>Не найден экран: '+screenname+'</h1>','tabid':self.current_tab_id},room=self.sid,namespace='/'+SOCKET_NAMESPACE)
            else:  
              self.hashMap.pop('ShowScreen',None)    
              soup = bs4.BeautifulSoup(features="lxml")
              
              self.added_tables=[]
              self.firsttabslayout=[]
              self.screentabs=[]
              
              self.screen=screen
              
              self.RunEvent("onStart")

 
              layots = self.get_layouts(soup,screen,0)

              self.socket_.emit('setvaluehtml', {'key':"root_"+self.current_tab_id,'value':str(layots),'tabid':self.current_tab_id},room=self.sid,namespace='/'+SOCKET_NAMESPACE)
                          
              

              for t in self.added_tables:
                self.socket_.emit('run_datatable', t,room=self.sid,namespace='/'+SOCKET_NAMESPACE) 

              if not "SelectTab" in self.hashMap:
                for t in self.firsttabslayout:
                  self.socket_.emit('click_button', {"id":t},room=self.sid,namespace='/'+SOCKET_NAMESPACE)  

              self.RunEvent("onPostStart")

    for k,v in list(self.hashMap.items()):
       if len(k)>8:
        if k[:8]=="SetShow_":
            value1="visible"
            value2 = "block"
            if v=='1':
              value1="visible"
              value2 = "block"
            elif   v=='0':
              value1="hidden"
              value2 = "block"
            elif   v=='-1':
              value1="collapse"
              value2 = "none" 
              
            self.socket_.emit('setvisible', {'key':"d"+self.current_tab_id+"_"+k[8:],'value1':value1,'value2':value2,'tabid':self.current_tab_id},room=self.sid,namespace='/'+SOCKET_NAMESPACE) 
            if k in self.hashMap:
              del self.hashMap[k]
          

    self.tabsHashMap[active_tab]=dict(self.hashMap)            
    if need_run_on_start:
       self.added_tables=[]
       self.firsttabslayout=[]
       self.screentabs = [] 
       self.RunEvent("onStart")
       layots = self.get_layouts(soup,self.screen,0)
       self.socket_.emit('setvaluehtml', {'key':"root_"+tabid,'value':str(layots),'tabid':tabid},room=self.sid,namespace='/'+SOCKET_NAMESPACE)

       for t in self.added_tables:
          self.socket_.emit('run_datatable', t,room=self.sid,namespace='/'+SOCKET_NAMESPACE) 

       if not "SelectTab" in self.hashMap:
        for t in self.firsttabslayout:
          self.socket_.emit('click_button', {"id":t},room=self.sid,namespace='/'+SOCKET_NAMESPACE) 

       self.RunEvent("onPostStart")

  def __init__(self,socket,pyton_path):

    fullpath = Simple.PYTHONPATH+os.sep+ 'current_handlers.py'

    path = pathlib.Path(fullpath)

    if path.exists():

      sys.path.append(pyton_path)
      module = __import__('current_handlers')
      import importlib
      importlib.reload(module) 

    self.socket_ = socket

    self.isreload=False
    self.islogin=False
    self.loginreload=False

    self.configuration = {}
    self.hashMap={}
    self.hashMapGlobals={}



    self.current_tab_id=None

    self.js_results = {}
    self.js_results_async = {}

    self.opened_tabs =[]
    self.new_tabs = []

    self.parent_tab_id=None

    Simple.PYTHONPATH=pyton_path

    self.hashMap["base_path"] = Simple.PYTHONPATH

    

    self.screen=None
    self.process=None
    self.tabs={}

    self.tabsHashMap={}

    self.added_tables = []
    self.added_canvas = []
    
    
    self.blocknext=False

    self.firsttabslayout=[]
    self.screentabs = []

    self.modal =""


    self.url=''
    self.urlonline=''

    self.username=""
    self.password=""

    self.sid=None

    self.menutemplate=None

    self.process_data = {}


  


 
  def set_sid(self,sid):
    self.sid=sid

  def load_configuration(self,filename):
    fullfilename = Simple.PYTHONPATH+os.sep+filename

    try:
      with open(fullfilename, 'r',encoding='utf-8') as file:
          data = file.read()
      
          self.configuration =  json.loads(data)   
    except Exception as e:
      print(str(e))
      

    try:
      fullpath = Simple.PYTHONPATH+os.sep+ 'current_handlers.py'

      

      if os.path.exists(fullpath):

        sys.path.append(Simple.PYTHONPATH)
        module = __import__('current_handlers')
        import importlib
        importlib.reload(module)
    except Exception as e:
         print(str(e))
        



  def calculateField(self,val,localData):
   

    if val==None: 
        return ''

    if len(val)==0:
        return ''

    if val[0]=='@':
        var = val[1:]

        #result = next((item for item in hashMap if item["key"] == var), None)
        if not localData ==None:
          if var in localData:
              return str(localData[var]) 
          else:    
              return ""
        else:  
          if var in self.hashMap:
              return str(self.hashMap[var]) 
          else:    
              return ""

    else:
        return val 



  def get_layouts(self,soup,root,level,var_prefix='',localData=None):
    
    
    currentcontainer = bs4.BeautifulSoup(features="lxml")
    

    for elem in root['Elements']:
        tvkey = elem.get("Variable")
        if tvkey==None or tvkey=='':
           tvkey = ''

        tvkey=var_prefix+"d"+self.current_tab_id+"_"+tvkey

        #if orientation=="vertical":
        #           new_column = list() 
                   
        if elem.get('type')=='LinearLayout' or elem.get('type')=='Tabs' or elem.get('type')=='Tab':
            
            styles = []

            


            if "BackgroundColor" in elem:
                  if len(elem.get("BackgroundColor",""))>0:
                    styles.append("background-color:"+elem.get("BackgroundColor")) 

            if "StrokeWidth" in elem:
                  if len(elem.get("StrokeWidth",""))>0:
                    styles.append("border:"+str(elem.get("StrokeWidth"))+ "px solid #242222;")

            if "Padding" in elem:
                  if len(elem.get("Padding",""))>0:
                    styles.append("padding:"+str(elem.get("Padding"))+ "px;")

            if elem.get('type')=='LinearLayout':  

              if elem.get("orientation")=='horizontal':
                if "gravity_horizontal" in  elem:
                  if  elem.get("gravity_horizontal")=='center':
                    styles.append("justify-content:center;")
                  elif  elem.get("gravity_horizontal")=='left':
                    styles.append("justify-content:flex-start;")  
                  elif  elem.get("gravity_horizontal")=='right':
                    styles.append("justify-content:flex-end;")
                if "gravity_vertical" in  elem:
                  if  elem.get("gravity_vertical")=='center':
                    styles.append("align-items:center;")
                  elif  elem.get("gravity_vertical")=='top':
                    styles.append("align-items:flex-start;")  
                  elif  elem.get("gravity_vertical")=='bottom':
                    styles.append("align-items:flex-end;")        


                if "width" in elem:
                      if str(elem.get("width","")).isnumeric():
                        styles.append("flex:"+str(elem.get("width"))+"px;")
                      elif  elem.get("width","")=="match_parent":
                        if str(elem.get("weight",""))=="0":
                          styles.append("flex:1;") 
                        elif len(str(elem.get("weight","")))>0:  
                          styles.append("flex:"+str(elem.get("weight",""))+";")
                        
                if "height" in elem:
                    if str(elem.get("height","")).isnumeric():
                      styles.append("height:"+str(elem.get("height"))+"px;")
                    elif  elem.get("height","")=="match_parent":
                      styles.append("height:100%;")        
              else:

                if "gravity_vertical" in  elem:
                  if  elem.get("gravity_vertical")=='center':
                    styles.append("justify-content:center;")
                  elif  elem.get("gravity_vertical")=='top':
                    styles.append("justify-content:flex-start;")  
                  elif  elem.get("gravity_vertical")=='bottom':
                    styles.append("justify-content:flex-end;")
                if "gravity_horizontal" in  elem:
                  if  elem.get("gravity_horizontal")=='center':
                    styles.append("align-items:center;")
                  elif  elem.get("gravity_horizontal")=='left':
                    styles.append("align-items:flex-start;")  
                  elif  elem.get("gravity_horizontal")=='right':
                    styles.append("align-items:flex-end;")   


                if "height" in elem:
                      if str(elem.get("height","")).isnumeric():
                        styles.append("flex:"+str(elem.get("height"))+"px;")
                      elif  elem.get("height","")=="match_parent":
                        if str(elem.get("weight",""))=="0":
                          styles.append("flex:1;") 
                        elif len(str(elem.get("weight","")))>0:  
                          styles.append("flex:"+str(elem.get("weight",""))+";") 
                if "width" in elem:
                    if str(elem.get("width","")).isnumeric():
                      styles.append("width:"+str(elem.get("width"))+"px;")
                    elif  elem.get("width","")=="match_parent":
                      styles.append("width:100%;")        

            if elem.get('type')=='Tab':        
              styles.append("width:100%;") 
              styles.append("height:100%;")


            for k,v in list(self.hashMap.items()):
              if len(k)>5:
                if k[:5]=="Show_":
                    if k[5:] in tvkey:
                      value1="visible"
                      value2 = "block"
                      if v=='1':
                        value1="visible"
                        value2 = "block"
                      elif   v=='0':
                        value1="hidden"
                        value2 = "block"
                      elif   v=='-1':
                        value1="collapse"
                        value2 = "none" 
                        
                      styles.append("visibility:"+value1+";")
                      styles.append("display:"+value2+";")
                      if k in self.hashMap:
                        del self.hashMap[k]  
                      

            stylestr = ";".join(styles)          
    
            if elem.get('type')=='LinearLayout':
              if elem.get("orientation")=='horizontal':
                  new_element = soup.new_tag("div",   **{'class':'container-horizontal'},style=stylestr,id=tvkey)
                  currentcontainer.append(new_element)
              else:
                  new_element = soup.new_tag("div",  **{'class':'container-vertical'},style=stylestr,id=tvkey)
                  currentcontainer.append(new_element)   

              layouts = self.get_layouts(soup,elem,level+1,var_prefix,localData)

              if 'style_class' in elem:
                    new_element['class'] = new_element.get('class', []) + [elem.get('style_class')]
                   
                  

              new_element.append(layouts)
            elif  elem.get('type')=='Tabs': 
               new_element = soup.new_tag("div",   **{'class':'tab'},style=stylestr,id="d"+self.current_tab_id+elem.get("Variable","defaulttabs"))
               i=1 
               fortab=""
               for item in elem['Elements']:
                idtab =  item.get("Variable","") 
                if len(idtab)>0:
                  #idtab ="d"+self.current_tab_id
                  idtab ="d"+self.current_tab_id+"_btn_"+item.get("Variable","")
                  idcontent = "d"+self.current_tab_id+item.get("Variable","")
                  #button = soup.new_tag("button",   **{'class':'tablinks'},style=stylestr,onclick="openTabLayout("+idtab+",event, '"+elem.get("Variable")+"_content_"+idtab+"')")
                  button = soup.new_tag("button",   **{'class':'tablinks'},style=stylestr,onclick="openTabLayout('"+idcontent+"',event, '"+idcontent+"')",id=idtab)

                  self.screentabs.append(idtab)

                  if i==1:
                    #fortab=idtab+"_btn_"+item.get("Variable","")
                    fortab = idtab
                    self.firsttabslayout.append(fortab)
                  button.string=item.get("Variable","defaulttabs")
                  i+=1
                  new_element.append(button)

               if 'style_class' in elem:
                    new_element['class'] = new_element.get('class', []) + [elem.get('style_class')]
                    
                 

               currentcontainer.append(new_element)

               layouts = self.get_layouts(soup,elem,level+1,var_prefix,localData) 
               currentcontainer.append(layouts)
              
            elif  elem.get('type')=='Tab': 
               idtab =  elem.get("Variable","") 
               if len(idtab)>0:
                idtab ="d"+self.current_tab_id+idtab
                new_element = soup.new_tag("div",   **{'class':'tabcontentlayout'},style=stylestr,id=idtab)
                
                if 'style_class' in elem:
                    new_element['class'] = new_element.get('class', []) + [elem.get('style_class')]
                    
                  

                layouts = self.get_layouts(soup,elem,level+1,var_prefix,localData)
                new_element.append(layouts)

                currentcontainer.append(new_element)

                #new_tag = soup.new_tag("script" )
                #new_tag.string = 'document.getElementById("'+var_prefix+'").click();'
                #currentcontainer.append(new_tag)

        else:  
            additional_styles=[]
            for k,v in list(self.hashMap.items()):
              if len(k)>5:
                if k[:5]=="Show_":
                    if k[5:] in tvkey or k[5:] in tvkey+"_div":
                      value1="visible"
                      value2 = "block"
                      if v=='1':
                        value1="visible"
                        value2 = "block"
                      elif   v=='0':
                        value1="hidden"
                        value2 = "block"
                      elif   v=='-1':
                        value1="collapse"
                        value2 = "none" 
                        
                      additional_styles.append("visibility:"+value1+";")
                      additional_styles.append("display:"+value2+";")
                      if k in self.hashMap:
                        del self.hashMap[k] 

            addstylestr = ";".join(additional_styles)

 
 
            if elem.get('type')=='TextView':
                
                  new_element = soup.new_tag("p", id=tvkey,style=get_decor(elem,additional_styles))

                  new_element.string = html.unescape(self.calculateField(elem.get("Value"),localData))

                  if 'style_class' in elem:
                    new_element['class'] = new_element.get('class', []) + [elem.get('style_class')]

                  if "#" in str(self.calculateField(elem.get("Value"),localData)):
                    new_element['class'] = new_element.get('class', []) + ['fa']

                  currentcontainer.append(new_element)
                        
                

            if elem.get('type')=='EditTextText':
                
              if "|" in elem.get("Value",''):
                    splited =  elem.get("Value",'').split("|")

                    new_element_layout = soup.new_tag("div",   **{'class':'container-horizontal'},id=tvkey+"_div")

                    new_element = soup.new_tag("p", style=get_decor(elem,additional_styles),id=tvkey+"_p")

                    new_element.string = html.unescape(self.calculateField(splited[0],localData))

                    if 'style_class' in elem:
                      new_element['class'] = new_element.get('class', []) + [elem.get('style_class')]

                    if "#" in str(self.calculateField(splited[0],localData)):
                      new_element['class'] = new_element.get('class', []) + ['fa']

                    new_element_layout.append(new_element)

                    new_element = soup.new_tag("input", id=tvkey,type="text",style=get_decor(elem,additional_styles))
                    if len(splited[1])>0:
                      new_element = soup.new_tag("input", id=tvkey,type="text",value = self.calculateField(splited[1],localData),style=get_decor(elem,additional_styles))
                    
                    new_element_layout.append(new_element)

                    currentcontainer.append(new_element_layout)

              else:    

                
                new_element = soup.new_tag("input", id=tvkey,type="text",style=get_decor(elem,additional_styles))
                if len(elem.get("Value",''))>0:
                  new_element = soup.new_tag("input", id=tvkey,type="text",value = self.calculateField(elem.get("Value"),localData),style=get_decor(elem,additional_styles))
                
                currentcontainer.append(new_element)

            if elem.get('type')=='EditTextAuto':
                
              if "|" in elem.get("Value",''):
                    splited =  elem.get("Value",'').split("|")

                    new_element_layout = soup.new_tag("div",   **{'class':'container-horizontal'},id=tvkey+"_div")

                    new_element = soup.new_tag("p", style=get_decor(elem,additional_styles),id=tvkey+"_p")

                    new_element.string = html.unescape(self.calculateField(splited[0],localData))

                    if 'style_class' in elem:
                      new_element['class'] = new_element.get('class', []) + [elem.get('style_class')]

                    if "#" in str(self.calculateField(splited[0],localData)):
                      new_element['class'] = new_element.get('class', []) + ['fa']

                    new_element_layout.append(new_element)

                    new_element = soup.new_tag("input", id=tvkey,type="text",style=get_decor(elem,additional_styles), **{'class':'autotext'})
                    if len(splited[1])>0:
                      new_element = soup.new_tag("input", id=tvkey,type="text",value = self.calculateField(splited[1],localData), **{'class':'autotext'},style=get_decor(elem,additional_styles))
                      
                    if 'style_class' in elem:
                        new_element['class'] = new_element.get('class', []) + [elem.get('style_class')]
                    
                    new_element_layout.append(new_element)

                    currentcontainer.append(new_element_layout)

              else:    

                new_element = soup.new_tag("input", id=tvkey,type="text",style=get_decor(elem,additional_styles), **{'class':'autotext'})
                if len(elem.get("Value",''))>0:
                  new_element = soup.new_tag("input", id=tvkey,type="text",value = self.calculateField(elem.get("Value"),localData), **{'class':'autotext'},style=get_decor(elem,additional_styles))
                  
                if 'style_class' in elem:
                    new_element['class'] = new_element.get('class', []) + [elem.get('style_class')]
                    
                  
                
                currentcontainer.append(new_element)
            

            if elem.get('type')=='EditTextNumeric':

                step ="any"
                placeholder="0."

                if int(elem.get('NumberPrecision','-1'))>=0:
                  if int(elem.get('NumberPrecision','-1'))==0:
                    step="1"
                  else:
                    step="."  
                    for i in range(1,int(elem.get('NumberPrecision','-1'))):
                      step+="0"
                      placeholder+="0"

                    step+="1"  
                    placeholder+="0"

                if "|" in elem.get("Value",''):
                    splited =  elem.get("Value",'').split("|")

                    new_element_layout = soup.new_tag("div",   **{'class':'container-horizontal'},id=tvkey+"_div")

                    new_element = soup.new_tag("p", style=get_decor(elem,additional_styles),id=tvkey+"_p")

                    new_element.string = html.unescape(self.calculateField(splited[0],localData))

                    if 'style_class' in elem:
                      new_element['class'] = new_element.get('class', []) + [elem.get('style_class')]

                    if "#" in str(self.calculateField(splited[0],localData)):
                      new_element['class'] = new_element.get('class', []) + ['fa']

                    new_element_layout.append(new_element)

                    new_element = soup.new_tag("input", id=tvkey,type="number",style=get_decor(elem,additional_styles), onkeypress="return isNumberKey(event)",step=step,placeholder=placeholder)
                    
                    if len(splited[1])>0:
                      new_element = soup.new_tag("input", id=tvkey,type="number",value = self.calculateField(splited[1],localData),step=step,placeholder=placeholder,style=get_decor(elem,additional_styles))
                      
                    if 'style_class' in elem:
                        new_element['class'] = new_element.get('class', []) + [elem.get('style_class')]
                    
                    new_element_layout.append(new_element)

                    currentcontainer.append(new_element_layout)

                else:    

                  
                  new_element = soup.new_tag("input", id=tvkey,type="number",style=get_decor(elem,additional_styles), onkeypress="return isNumberKey(event)",step=step,placeholder=placeholder)
                  if len(elem.get("Value",''))>0:
                    new_element = soup.new_tag("input", id=tvkey,type="number",value = self.calculateField(elem.get("Value"),localData),step=step,placeholder=placeholder,style=get_decor(elem,additional_styles))
                    
                  if 'style_class' in elem:
                      new_element['class'] = new_element.get('class', []) + [elem.get('style_class')]
                      
                  
                
                  currentcontainer.append(new_element)    

            if elem.get('type')=='EditTextPass':
                
                if "|" in elem.get("Value",''):
                    splited =  elem.get("Value",'').split("|")

                    new_element_layout = soup.new_tag("div",   **{'class':'container-horizontal'},id=tvkey+"_div")

                    new_element = soup.new_tag("p", style=get_decor(elem,additional_styles),id=tvkey+"_p")

                    new_element.string = html.unescape(self.calculateField(splited[0],localData))

                    if 'style_class' in elem:
                      new_element['class'] = new_element.get('class', []) + [elem.get('style_class')]

                    if "#" in str(self.calculateField(splited[0],localData)):
                      new_element['class'] = new_element.get('class', []) + ['fa']

                    new_element_layout.append(new_element)

                    new_element = soup.new_tag("input", id=tvkey,type="password",style=get_decor(elem,additional_styles))
                    if len(splited[1])>0:
                      new_element = soup.new_tag("input", id=tvkey,type="password",value = self.calculateField(splited[1],localData),style=get_decor(elem,additional_styles))
                      
                    if 'style_class' in elem:
                        new_element['class'] = new_element.get('class', []) + [elem.get('style_class')]
                    
                    new_element_layout.append(new_element)

                    currentcontainer.append(new_element_layout)

                else:
                  
                  new_element = soup.new_tag("input", id=tvkey,type="password",style=get_decor(elem,additional_styles))
                  if len(elem.get("Value",''))>0:
                    new_element = soup.new_tag("input", id=tvkey,type="password",value = self.calculateField(elem.get("Value"),localData),style=get_decor(elem,additional_styles))
                    
                  if 'style_class' in elem:
                      new_element['class'] = new_element.get('class', []) + [elem.get('style_class')]
                    
                currentcontainer.append(new_element)

            if elem.get('type')=='MultilineText':

                
                #new_form = soup.new_tag("form", method="post", action="/oninput/")  


                   

                 if "|" in elem.get("Value",''):
                    splited =  elem.get("Value",'').split("|")

                    new_element_layout = soup.new_tag("div",   **{'class':'container-horizontal'},id=tvkey+"_div")

                    new_element = soup.new_tag("p", style=get_decor(elem,additional_styles),id=tvkey+"_p")

                    new_element.string = html.unescape(self.calculateField(splited[0],localData))

                    if 'style_class' in elem:
                      new_element['class'] = new_element.get('class', []) + [elem.get('style_class')]

                    if "#" in str(self.calculateField(splited[0],localData)):
                      new_element['class'] = new_element.get('class', []) + ['fa']

                    new_element_layout.append(new_element)

                    additional_styles.append("resize: both;")   
                    additional_styles.append("overflow: auto;")

                    new_element = soup.new_tag("textarea", id=tvkey,style=get_decor(elem,additional_styles))
                    if len(splited[1])>0:
                      new_element.string =  self.calculateField(splited[1],localData)
                      
                    if 'style_class' in elem:
                        new_element['class'] = new_element.get('class', []) + [elem.get('style_class')]
                
                    new_element_layout.append(new_element)

                    currentcontainer.append(new_element_layout)

                 else:    

                  additional_styles.append("resize: both;")
                  additional_styles.append("overflow: auto;")
                
                  new_element = soup.new_tag("textarea", id=tvkey,style=get_decor(elem,additional_styles))
                  if len(elem.get("Value",''))>0:
                    new_element.string =  self.calculateField(elem.get("Value"),localData)
                    
                  if 'style_class' in elem:
                      new_element['class'] = new_element.get('class', []) + [elem.get('style_class')]
               
                  currentcontainer.append(new_element)
            
            if elem.get('type')=='file':

                
                #new_form = soup.new_tag("form", method="post", action="/oninput/")  
                
                new_element = soup.new_tag("input", id=tvkey,type="file",style=get_decor(elem))
                if len(elem.get("Value",''))>0:
                  new_element = soup.new_tag("input", id=tvkey,type="file",value = self.calculateField(elem.get("Value"),localData),style=get_decor(elem,additional_styles))
                  
                
                #new_form.append(new_element)
                currentcontainer.append(new_element)

            if elem.get('type')=='DateField':
                
                if "|" in elem.get("Value",''):
                    splited =  elem.get("Value",'').split("|")

                    new_element_layout = soup.new_tag("div",   **{'class':'container-horizontal'},id=tvkey+"_div")

                    new_element = soup.new_tag("p",style=get_decor(elem,additional_styles),id=tvkey+"_p")

                    new_element.string = html.unescape(self.calculateField(splited[0],localData))

                    if 'style_class' in elem:
                      new_element['class'] = new_element.get('class', []) + [elem.get('style_class')]

                    if "#" in str(self.calculateField(splited[0],localData)):
                      new_element['class'] = new_element.get('class', []) + ['fa']

                    new_element_layout.append(new_element)

                    new_element = soup.new_tag("input", id=tvkey,type="date",style=get_decor(elem,additional_styles))
                    if len(splited[1])>0:
                      new_element = soup.new_tag("input", id=tvkey,type="date",value = self.calculateField(splited[1],localData),style=get_decor(elem,additional_styles))
                      
                    if 'style_class' in elem:
                        new_element['class'] = new_element.get('class', []) + [elem.get('style_class')]
                    
                    new_element_layout.append(new_element)

                    currentcontainer.append(new_element_layout)

                else:
                  
                  new_element = soup.new_tag("input", id=tvkey,type="date",style=get_decor(elem))
                  if len(elem.get("Value",''))>0:
                    new_element = soup.new_tag("input", id=tvkey,type="date",value = self.calculateField(elem.get("Value"),localData),style=get_decor(elem,additional_styles))
                    
                  if 'style_class' in elem:
                      new_element['class'] = new_element.get('class', []) + [elem.get('style_class')]
                      
                  currentcontainer.append(new_element)    

            if elem.get('type')=='SpinnerLayout':

                if len(elem.get("Value",''))>0:
                  if "|" in elem.get("Value",''):
                    splited =  elem.get("Value",'').split("|")

                    new_element_layout = soup.new_tag("div",   **{'class':'container-horizontal'},id=tvkey+"_div",style=addstylestr)

                    new_element = soup.new_tag("p", style=get_decor(elem,additional_styles),id=tvkey+"_p")

                    new_element.string = html.unescape(self.calculateField(splited[0],localData))

                    if 'style_class' in elem:
                      new_element['class'] = new_element.get('class', []) + [elem.get('style_class')]

                    if "#" in str(self.calculateField(splited[0],localData)):
                      new_element['class'] = new_element.get('class', []) + ['fa']

                    new_element_layout.append(new_element)


                    values = self.calculateField(splited[1],localData).split(";")

                    new_element = soup.new_tag("select", id=tvkey,style=get_decor(elem,additional_styles))
                    

                    currentcontainer.append(new_element)
                    #,list="list"+tvkey
                    #new_element = soup.new_tag("datalist", id="list"+tvkey,style=get_decor(elem))
                    for el in values:
                      value = html.unescape(self.calculateField("@"+elem.get("Variable",''),localData))
                      if value == el:
                        new_option = soup.new_tag("option", selected = "selected")
                      else:  
                        new_option = soup.new_tag("option")
                      new_option.string=el
                      
                      new_element.append(new_option)
                      
                    if 'style_class' in elem:
                        new_element['class'] = new_element.get('class', []) + [elem.get('style_class')]
                        
                      
                    #new_form.append(new_element)
                    new_element_layout.append(new_element)

                    currentcontainer.append(new_element_layout)
                    
                  else:   



                    values = self.calculateField(elem.get("Value",''),localData).split(";")
                
                
                    new_element = soup.new_tag("select", id=tvkey,style=get_decor(elem,additional_styles),value = html.unescape(self.calculateField("@"+elem.get("Variable",''),localData)),selected="selected")
                    

                    currentcontainer.append(new_element)
                    #,list="list"+tvkey
                    #new_element = soup.new_tag("datalist", id="list"+tvkey,style=get_decor(elem))
                    for el in values:
                      value = html.unescape(self.calculateField("@"+elem.get("Variable",''),localData))
                      if value == el:
                        new_option = soup.new_tag("option", selected = "selected")
                      else:  
                        new_option = soup.new_tag("option")
                        
                      new_option.string=el
                      
                      new_element.append(new_option)
                      
                    if 'style_class' in elem:
                        new_element['class'] = new_element.get('class', []) + [elem.get('style_class')]
                        
                      
                    #new_form.append(new_element)
                    currentcontainer.append(new_element)    

                    

                    
            if elem.get('type')=='html':
                
                  new_element = soup.new_tag("div",   id=tvkey)

                  new_element.string = html.unescape(self.calculateField(elem.get("Value"),localData))

                  if 'style_class' in elem:
                    new_element['class'] = new_element.get('class', []) + [elem.get('style_class')]

                  

                  currentcontainer.append(new_element)

            if elem.get('type')=='map':

              if tvkey!=""  and tvkey!=None:
                
                new_element = soup.new_tag("canvas", id=tvkey,style=get_decor(elem,additional_styles)+";border: 1px solid gray;")
                  
                    
                if 'style_class' in elem:
                      new_element['class'] = new_element.get('class', []) + [elem.get('style_class')]

                currentcontainer.append(new_element)
                
                self.added_canvas.append(tvkey)

            if elem.get('type')=='CheckBox':

                
                new_element_layout = soup.new_tag("div",   **{'class':'container-horizontal'},id=tvkey+"_div")
                
                new_element = soup.new_tag("input", id=tvkey,type="checkbox",style=get_decor(elem,additional_styles))
                if str(self.calculateField("@"+elem.get("Variable",''),localData)).lower()=='true':
                  new_element = soup.new_tag("input", id=tvkey,type="checkbox",style=get_decor(elem,additional_styles),checked=True)
                else:
                  new_element = soup.new_tag("input", id=tvkey,type="checkbox",style=get_decor(elem,additional_styles))  
                  
                if 'style_class' in elem:
                    new_element['class'] = new_element.get('class', []) + [elem.get('style_class')]
                 
                  
                
               
                new_element_layout.append(new_element)

                new_element = soup.new_tag("p", style=get_decor(elem,additional_styles),id=tvkey+"_p")

                new_element.string = html.unescape(self.calculateField(elem.get("Value"),localData))

                if 'style_class' in elem:
                  new_element['class'] = new_element.get('class', []) + [elem.get('style_class')]

                if "#" in str(self.calculateField(elem.get("Value"),localData)):
                  new_element['class'] = new_element.get('class', []) + ['fa']

                new_element_layout.append(new_element)

                currentcontainer.append(new_element_layout)
            
            if elem.get('type')=='Button':
                #new_form = soup.new_tag("form", method="post", action="/oninput/")
                #new_element = soup.new_tag("button", id=tvkey,onclick="myFunction(this,555)")
                
                  #additional_styles.append()
                  new_element = soup.new_tag("button", id=tvkey,style=get_decor(elem,additional_styles))
                  new_element.string = html.unescape(self.calculateField(elem.get("Value"),localData))
                  
                  if 'style_class' in elem:
                    new_element['class'] = new_element.get('class', []) + [elem.get('style_class')]

                  if "#" in str(self.calculateField(elem.get("Value"),localData)):
                    new_element['class'] = new_element.get('class', []) + ['fa']


                  #new_form.append(new_element)
                  currentcontainer.append(new_element)


            if elem.get('type')=='Picture':
                
                img_value =self.calculateField(elem.get("Value"),localData)
                if len(img_value)>0:
                  if len(img_value)<150 or img_value[0]=="~":
                    if  img_value[0]=="~":
                      new_element = soup.new_tag("img", id=tvkey,style=get_decor(elem,additional_styles),src="/static/"+img_value[1:])
                    else:
                      new_element = soup.new_tag("img", id=tvkey,style=get_decor(elem,additional_styles),src="/static/"+img_value)  
                        
                  else:
                    new_element = soup.new_tag("img", id=tvkey,style=get_decor(elem,additional_styles),src="data:image/png;base64,"+img_value)   
                  
                  
                  if 'style_class' in elem:
                      new_element['class'] = new_element.get('class', []) + [elem.get('style_class')]
                      
                
                  
                  currentcontainer.append(new_element)    

            if elem.get('type')=='TableLayout':
                if not elem.get("Value")==None:

                  styles = []
                  if "width" in elem:
                    if str(elem.get("width","")).isnumeric():
                      styles.append("width:"+str(elem.get("width"))+"px")
                    elif  elem.get("width","")=="match_parent":
                      styles.append("width:100%")

                  if "height" in elem:
                    if str(elem.get("height","")).isnumeric():
                      styles.append("height:"+str(elem.get("height"))+"px")
                    elif  elem.get("height","")=="match_parent":
                      styles.append("height:100%")   

                  
                  stylestr = ";".join(styles)   

                  htmltable = self.add_table(self.calculateField(elem.get("Value"),localData),tvkey,stylestr)
                  if not htmltable == None:
                    currentcontainer.append(htmltable)
            if elem.get('type')=='CardsLayout':

                styles = []

                

                if "BackgroundColor" in elem:
                  if len(elem.get("BackgroundColor",""))>0:
                    styles.append("background-color:"+elem.get("BackgroundColor")) 

              

                if "width" in elem:
                  if str(elem.get("width","")).isnumeric():
                    styles.append("width:"+str(elem.get("width"))+"px")
                  elif  elem.get("width","")=="match_parent":
                    styles.append("width:100%")

                if "height" in elem:
                  if str(elem.get("height","")).isnumeric():
                    styles.append("height:"+str(elem.get("height"))+"px")
                  elif  elem.get("height","")=="match_parent":
                    styles.append("height:100%")   

                styles.append("overflow-y: scroll;")   

                stylestr = ";".join(styles)

                if not elem.get("Value")==None:
                  htmlcards = self.add_cards(self.calculateField(elem.get("Value"),localData),tvkey,stylestr)
                  if not htmlcards == None:
                    currentcontainer.append(htmlcards)      


    # if level==0:
    #    resultcontainer = bs4.BeautifulSoup(features="lxml")  
    #    if root.get("orientation")=='horizontal':
    #             new_element = resultcontainer.new_tag("div",   **{'class':'container-horizontal'})
    #             resultcontainer.append(new_element)
    #    else:
    #             new_element = resultcontainer.new_tag("div",  **{'class':'container-vertical'})
    #             resultcontainer.append(new_element)           

    #    resultcontainer.append(currentcontainer)

    #    currentcontainer=resultcontainer

    return bs4.BeautifulSoup(html.unescape(str(currentcontainer)),features='lxml')





  def add_cards(self,value,variable,stylestr):

   if variable==None or variable=="":
      variable = "cards_"+str(uuid.uuid4().hex)
    
   try:
    jcards = json.loads(value)

    basic="""<div class="cards" id=#cardsdiv #style">   
  </div>    """

    
    basic =basic.replace("#cardsdiv","cardsdiv_"+variable)
    basic =basic.replace("#style",'style="'+stylestr+'"')
    base = bs4.BeautifulSoup(basic,features="lxml")

    root = base.find(id="cardsdiv_"+variable)

    i=0
    for datarow in jcards['customcards']['cardsdata']:
      rowid="cardrow_"+str(i)+"_"+variable
      row=base.new_tag("div",  **{'class':'card shadow-1'},id=rowid)
      i+=1

      layout = self.get_layouts(base,jcards['customcards']['layout'],0,rowid+"_",datarow)
      row.append(layout)



      root.append(row)
    
    

    return base.body

   except:
      return None


      
  def add_table(self,value,variable,stylestr=None):
    

    if variable==None or variable=="":
      variable = "table_"+str(uuid.uuid4().hex)
    
    try:
      jtable = json.loads(value)
      
      basic_table = """
      
            <div class="container" id="#tablediv">
                

            </div>
            <script type="text/javascript" charset="utf8" src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
            <script type="text/javascript" charset="utf8" src="https://cdn.datatables.net/1.10.25/js/jquery.dataTables.js"></script>
            <script type="text/javascript" charset="utf8" src="https://cdn.datatables.net/1.10.25/js/dataTables.bootstrap5.js"></script>
            
            
   
            """

      basic_table = """
      
            <div class="container" id="#tablediv">
                

            </div>
            
            
            
   
            """

      basic_table =basic_table.replace("#data","#"+variable)
      basic_table =basic_table.replace("#tablediv","tablediv_"+variable)

      

      list_columns="["
      for column in jtable['columns']:
        sep=""
        if len(list_columns)>3:
          sep =","
        list_columns+=sep+"{orderable: true, searchable: true}"  
      
      list_columns+="]"

      basic_table =basic_table.replace("#coumnssettings",list_columns)  

      

      base = bs4.BeautifulSoup(basic_table,features="lxml")

      useDatatable=False
      if 'useDataTable' in jtable:
        if str(jtable.get("useDataTable")).lower()=="true":
          useDatatable=True

      hideInterline=False
      if 'hideinterline' in jtable:
        if str(jtable.get("hideinterline")).lower()=="true":
          hideInterline=True    

      hideCaption=False
      if 'hidecaption' in jtable:
        if str(jtable.get("hidecaption")).lower()=="true":
          hideCaption=True       

      rootdiv = base.find(id="tablediv_"+variable)

      if hideInterline:
          table_element = base.new_tag("table", id=variable)
      else:  
          table_element = base.new_tag("table", id=variable,  **{'class':'table-striped'})
      
      if useDatatable:
       
        self.added_tables.append({"id":variable,"columns":list_columns})
      

      if stylestr ==None:
        table_element.attrs['style'] ="width: 100%;"
      else: 
        table_element.attrs['style'] =stylestr
      
      thead = base.new_tag("thead")

      totalsum=0
      for column in jtable['columns']:
        if "weight" in column:
          totalsum+=float(column['weight'])
        else:  
          totalsum+=1

      if not hideCaption:
        tr = base.new_tag("tr")
        for column in jtable['columns']:
          if "weight" in column:
            perc=round(100*float(column['weight'])/totalsum)
          else:  
            perc=round(100*1/totalsum)
          style="width:"+str(perc)+"%;"
          
          new_column = base.new_tag("th",style =style)
          
          new_column.string = column['header']
          tr.append(new_column)

        thead.append(tr)

        table_element.append(thead)


      editmode = jtable.get("editmode",'table')



      tbody = base.new_tag("tbody")
      i=0
      for row in jtable['rows']:
        #f = "tableClick("+str(i)+")"
        
        tr=base.new_tag("tr", id="tr_"+str(i)+"_"+variable)
        i+=1
        item_head = None
        
        ic=0
        for column in jtable['columns']:
          for key, value in row.items():
            if key==column['name']:
              
              item_head = column
              css_gravity="text-align: center;"
              if item_head.get("gravity",'')=="left":
                css_gravity="text-align: left;"
              elif item_head.get("gravity",'')=="right":
                css_gravity="text-align: right;" 

              if 'colorcells' in jtable:
                for c in jtable['colorcells']:
                  if str(c.get('row'))==str(i-1) and  str(c.get('column'))==str(ic):
                    css_gravity+="background-color:"+c.get('color','')+";"
                    break


              ic+=1
              if 'input' in column and editmode=='table':
                new_column = base.new_tag("td",style=css_gravity,contenteditable=True)     
              else:  
                new_column = base.new_tag("td",style=css_gravity)     
              
              
              if 'input' in column:
                if column['input']=="EditTextText":
                  #new_input = base.new_tag("input",style=css_gravity,type="checkbox",value=row[item_head['name']]) 
                  #new_input = base.new_tag("input",style=css_gravity,type="checkbox",checked=True) 
                  #new_column.append(new_input)
                  new_column.string = row[item_head['name']] 
                if column['input']=="CheckBox":
                  new_input = base.new_tag("input",style=css_gravity,type="checkbox",value=row[item_head['name']]) 
                  if str(row[item_head['name']]).lower()=="true":
                      new_input.attrs['checked']=True
                  #new_input = base.new_tag("input",style=css_gravity,type="checkbox",checked=row[item_head['name']]) 
                  new_column.append(new_input)
                  
              else:
                if isinstance(row[item_head['name']],bool):
                   if row[item_head['name']]==True:
                      new_column.string =u'\u2611'
                   else:   
                      new_column.string ='☐'
                else:   
                  new_column.string = str(row[item_head['name']])

              tr.append(new_column)

              break


        tbody.append(tr)
      
      table_element.append(tbody)

      rootdiv.append(table_element)

      return base.body

    except Exception as e:
      print(e)
      return None



  def build_page(self):
  
    

    self.added_tables.clear()
    self.firsttabslayout.clear()
    self.screentabs.clear()

    # <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.1.1/css/bootstrap.min.css">
    # <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.0.1/dist/css/bootstrap.min.css" rel="stylesheet" integrity="sha384-+0n0xVW2eSR5OomGNYDnhzAbDsOXxcvSN1TPprVMTNDbiYZCxYbOOl7+AMvyTG2x" crossorigin="anonymous">
    # <link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/1.10.25/css/dataTables.bootstrap5.css">
    # <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/css/font-awesome.min.css">

    # <meta name="viewport" content="width=device-width, initial-scale=1">

    # <script src="//code.jquery.com/jquery-1.12.4.min.js"></script>
    # <script src="//cdnjs.cloudflare.com/ajax/libs/socket.io/4.2.0/socket.io.js"></script>

    # <script src="https://ajax.googleapis.com/ajax/libs/jquery/2.1.1/jquery.min.js"></script>
    # <script src="http://code.jquery.com/jquery-latest.min.js"     type="text/javascript" charset="utf-8"></script>
    # <script	src="https://code.jquery.com/ui/1.12.1/jquery-ui.min.js" 			  type="text/javascript" charset="utf-8"></script>

    # <script type="text/javascript" charset="utf8" src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    # <script type="text/javascript" charset="utf8" src="https://cdn.datatables.net/1.10.25/js/jquery.dataTables.js"></script>
    # <script type="text/javascript" charset="utf8" src="https://cdn.datatables.net/1.10.25/js/dataTables.bootstrap5.js"></script>


    source = """<!DOCTYPE html>
    
    <html>
    <head>
    
    <title>Simple</title>

    <link rel="icon" type="image/png" sizes="16x16" href="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAEgAAABICAYAAABV7bNHAAAI7UlEQVR42u1ca0xURxTeXRYWqAgCdctTBYtSQFqBRkyLqAmPgiVNhGqCidgqPxpoamolkTb1B20T/uAvY9KgiWmiiIQ+pAVaEiK1IfGPRk0soUKsvKIIVF7CMp2znjHDzb1zd+8+YBdu8mVh996553z3nDNnZs5cnW5pDz3CoAD2+4o5QFkfCiN+2nrw13gdYQZUzqDwu4kinCKGIh4Rg9+ZNLbpEQd76vwRRrGb4guKixR/UvRSPKaYpJhFTOJ3vXgOnHsCrw2TtGmvNS75YZS4gZniI4qfKIYpiIOANn7ENs0S9zUud4vhTT6Top5iVKKghWKegwWxIIFF5twFSVujeI9Mifv5LEerYUc2RbtEEZ4MRy2IJ43/vh3vLSfTkgZgZjWbKK7IELPgBFKUsCBD1BWURSqf2w9f7u9PKaYlQruSGCWi2D1nUCY5Wd1KTjDFL5ygc24kRQm8DNdQRreSxG6UTNHHCWVZBuTwcYoRBTKmuIskFvhy0YyXi9WoWRPImufq4M3Y3y8JwmSZg5fxQ1dZEmswx8PIkZP1PWeTZORizowHkiMlCXR401nuxnKItSwg79mzZz4nJ4coITw8XLMSJpOJ7N27V7Ht7OxsEhISoni9Xq8nycnJitfn5ubOJyYmwrn9FOskOjpEEOvK50ZGRojFYlFEXl6eZoIiIyPJs2fPFNseGhoiO3fuVLzeaDSS+vp6oXx1dXUscP/KzUU55FqVfI/g6QSdOXOG790+1+pqbLC3kWKKyy28hSCWs4Fur0t0tougy9Jcx0sI4nVq4mY67XKtLG6cQ7yQIF63XHtcjQWtNrku3csIYrp12BqwmZm9LcOyN1sQQY9RjUXMxL5XSgi9jCBex4tqbsbM61WcMCdyI3QvJIjp+IQiWpQ8MuaOKJHjpQTxun4isiK2KNcsGm95KUFM1xalSX+2TBNKMbiCLQiWlCIknCyK3Lvleq4VQBCvc4Gcm7F/TqhNZ3gxQUznr+QWIdmi38VVgqzDq0VxSM+NRa6vEqT7i8KPL71hwcifokcUoL2cIKYzFEwE8YGaJUXrueKClUzQiDRhNHBzP+OrBOkmKLbIEZTATY6t5G4eONgmR9CWVYJeEpQqR1AcmpfQxYaHh5eUoMzMTFe72H8Ub/AEsV4swpYgPTg4KBQgPz/fZQTBvXfs2OGOIL2R78UYQUG2dPMPHz4UClBQUKCZoKioKDI1NaXY9sDAAMnIyHA1Qf/gmHQRQYBXKLrUEsWenh6hAEVFRZoJiomJITMzM4ptw8PZvn27qxPFblwoXVSjDVl0AMUPagTdunVLKEBxcbF1hVMLQfHx8UKCHjx4QFJSUlxNUCNy4SMdrEJ6Xa1GUGdnp1CAsrIyzQSlpqaS2dlZxbbv379PEhISXE3QN8iFUa6muUBNiebmZqEAx48fJwaDQRNBu3btIs+fP1ds+/bt2yQ2NtZVBDGUIBdG6YQZdGkbKAZEgfrs2bOqAoCgWggqKSkhc3Nzim13d3eT0NBQV06YDWHCbNDJbHkwYj3fzyI3O3XqlNANurq6rN21veSAcqdPnxYq19bWJiTfCVOusBYYojQnDV8GcsUKshZUWlpKxsfHFQV4+vQpOXjwoN1xCEjt6OgQKnfu3DlVkh20oCrkQLa4So8/JGKyJEsS5CH9/f1CIaCnwzocm+Dj40OqqqqESSK43rFjx1xBENPxMRZW+eoEO4r8MElSnFkMDg4mLS0tQiFAmZs3b1qDbmBgoLDgKSwsjFRWVpLR0VFhm319fcIk0QkLh1dQdz+1pWcwsUKlpWfooY4ePUqmp6eFgszPz1vzFnCLffv2kc2bN1urw9asWWOtQktKSiKHDx8mTU1NZGxsTNgWoKGhwfpwnEwQr9t+1F21gAH2aL1G8YeSFcFTb29vt5KgphgAgjpYCAw2YTwFA14gRdRj8ZiYmLBaoy2BXmPxwnUci5psLX+BcVmxyIqysrJIb2+vTQo6ArDUuro64ufn52yCeJ0Ooc42V77C/HQk7suSLRaHwAqupjb94QjAQhsbG0l0dLTNqYKGAqoW1NXf3gozYPQd0RwRkFRYWEju3r1rs7vYCnArUMZsNtuVS9lZgjeBi6VBWuoU/TEWfS1KHIGktLQ0cv78efLo0SOb45ISJicnyY0bN6zWqRaUNVa58rp8izoGaKly1SOzMNPYqrYvA7pzqGOGXuvOnTvCZFIKGH8Bua2traS8vNzqUloGvEBQTU0NuXfvnizA0qurq5kO0AnFo46ad1IbseA6FdeLVDevgJDQjaenp5MDBw6QkydPWp/ahQsXyKVLl8jly5etn2BxtbW1pKKiwjpNC1MdAQEBmmcCGCCYw8NSwBwGe5gUS0PdHN6SALmBGUf6E16wFQHmnItQp0Bn7deAGbZoGm+OcAHOEzezWGiKUq57sS9/rc6JLynQ4yh3I71BBUfSnAeQM8eR8xlOyK/TueANDgZsOI5a0sfcKqwnbKibQMuJw/GWyzb6QsPw5oNNlKT3MdixvGK5bcl8uUpBZf1A92IndJjODbugDfgUYPYxgys4Z09sYQmJWZBY9O9Y873B1ZYjF5Ng9jEKNtpR862hn2NLSJSUmDEq03e4mTcKZXX7W2P02E3CKDiB5j+5usVbxFnvYXGxK0l702tUljycW45AGZf0lTpG9O1YiiTq72X0s1NCjIUja8FBS7HIEA9/d9J7wwtPklCWMN0yetmJnksooafYRoUtpZ8NuFIgl5dIX26iBP5caTvQdgO91yEsWYnjEsBl+SImH0zAIlDYJGruu2k8+BLHc/86wa2gjd+gTWgbLSYO77lW5yHvEmLTJWbMWqH2KIUq9C7kUFS5Wvr/VSyY/BvX4p5gbjWOfw/gb3DOVbgGroU20Fq2oCuZ8V4e9ZIlPiUwYYJpxto/GEFvhd7P19f3LYoMUJoihxKQD4C/4Tv6Wzqco3uxJX0rXhuNba3Dtj36NV1SsvzwaYdi0ehr6BrRaA0bELH4XQSesx6vCcI2vIYUtcDOXtbmi9bgjzDhd0alZWB3Hf8DD16eCUpM7oQAAAAASUVORK5CYII=" />

    <script type="text/javascript" charset="utf8" src="https://code.jquery.com/jquery-3.6.0.min.js"></script>

    <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.1.1/css/bootstrap.min.css">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.0.1/dist/css/bootstrap.min.css" rel="stylesheet" integrity="sha384-+0n0xVW2eSR5OomGNYDnhzAbDsOXxcvSN1TPprVMTNDbiYZCxYbOOl7+AMvyTG2x" crossorigin="anonymous">
    <link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/1.10.25/css/dataTables.bootstrap5.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/css/font-awesome.min.css">

    <script src="https://maxcdn.bootstrapcdn.com/bootstrap/3.4.1/js/bootstrap.min.js"></script>

    <meta name="viewport" content="width=device-width, initial-scale=1">

    
    <script src="//cdnjs.cloudflare.com/ajax/libs/socket.io/4.2.0/socket.io.js"></script>

    <script src="//cdn.jsdelivr.net/jquery.color-animation/1/mainfile"></script> 

    <script src="https://cdn.jsdelivr.net/npm/js-cookie@3.0.5/dist/js.cookie.min.js"> </script>

    
    <script type="text/javascript" charset="utf8" src="https://cdn.datatables.net/1.10.25/js/jquery.dataTables.js"></script>
    <script type="text/javascript" charset="utf8" src="https://cdn.datatables.net/1.10.25/js/dataTables.bootstrap5.js"></script>
 
    <script>
    function isNumberKey(evt){
    var charCode = (evt.which) ? evt.which : evt.keyCode
    if (charCode > 31 && (charCode != 46 &&(charCode < 48 || charCode > 57)))
        return false;
    return true;
    }
    </script>
   
    </script>
    <script type="text/javascript" charset="utf-8">

        var canvas = [];

        $(document).ready(function() {

            

            namespace = '/simpleweb';
            var socket = io(namespace, {reconnection: false});
            var sid = socket.id

           
            var hashMap = {};
            var jsoutput = null;
            var nativehandlers = [];
            

            var DELAY = 250, clicks = 0, timer = null;
            
            var canvasevents=true;
                    
           

            let code = "";
            let reading = false;

            //#HTMLdocument_ready

            $(document).on('keypress',  function (e) {
            
              if (e.keyCode === 13) {
                      if(code.length > 10) {
                        console.log(code);
                        
                       
                        
                        formdata={data: 'barcode',barcode: code}
                        
                        if(performNativeJS("barcode","barcode",formdata)){
                        formdata["JSOutput"] = jsoutput;
                        socket.emit('input_event', formdata);
                        }

                         code = "";
                    }
                } else {
                    code += e.key;             
                }

                
                if(!reading) {
                    reading = true;
                    setTimeout(() => {
                        code = "";
                        reading = false;
                    }, 200); 
                }
              
            
            });

            function b64DecodeUnicode(str) {
    
                return decodeURIComponent(atob(str).split('').map(function(c) {
                    return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
                }).join(''));
            }


            function performNativeJS(event,id,data){
               let result=true;

               nativehandlers.forEach(function(obj) {
                  let mlistener = obj.listener.split('|'); 

                  if((mlistener.length==2 &&(mlistener[0]==event && id.includes(mlistener[1])))||(mlistener.length==1&&mlistener[0]==event)){
                  
                  let script = b64DecodeUnicode(obj.method);

                  
                  
                   try {

                      var F=new Function ('hashMap','id','data',script);
                      var r = F(hashMap,id,data);
                     
                      if(typeof(r)=="boolean")
                      {
                      result =  r;
                      }
                      else {
                      if(r instanceof Array)
                      {
                      if(r.length==2){
                      
                      jsoutput = r[1];
                      result =  r[0]
                      
                      }
                      else{
                      
                      result =  false;
                      
                      }
                      }
                      else{
                      result =  false;
                      }
                      }

                 } catch (err) { 
                      
                      alert("Errror:"+err);
                      result =  false;

                 }

                 

                  };
               });  

               return result; 
               
             }
            
           

            
             $(document).on('click', 'tr', function () {

              var id = $(this).attr("id")
              var index = $(this).index()
              var tableid = $(this).closest('table').attr("id")
              
               var selected = $('#'+id).hasClass("highlight");

                
                $("#"+tableid+" tr").removeClass("highlight");
                if(!selected)
                  $('#'+id).addClass("highlight");


                formdata={data: 'table_click_raw',index: index,source:id}
                if(performNativeJS("table_click_raw",id,formdata)){
                formdata["JSOutput"] = jsoutput;
                socket.emit('input_event', formdata);
                }

              clicks++;

              if(clicks === 1) {

                timer = setTimeout(function() {

                formdata={data: 'table_click',index: index,source:id}
                if(performNativeJS("table_click",id,formdata)){   
                formdata["JSOutput"] = jsoutput;
                socket.emit('input_event', formdata);
                }

                clicks = 0;  

                
                //$('#'+id).css({ "background-color": YOURCOLOR, "opacity": ".50" });
                //$('#'+id).toggleClass('highlight');

               
                
                         

            }, DELAY);

              } else {

                  clearTimeout(timer);    //prevent single-click action
                  
                  formdata={data: 'table_doubleclick',index: index,source:id}
                      
                  if(performNativeJS("table_doubleclick",id,formdata)){
                  formdata["JSOutput"] = jsoutput;
                  socket.emit('input_event', formdata);
                  }

                  clicks = 0;             
              }
                  
            



            });



            $(document).on('input','table td', function () {
              
              formdata={data: 'table_edit',index: ($(this).closest('tr').index()),source_row:($(this).closest('tr').attr("id")),source_column:($(this).index()),valuetext:($(this).text()),valuecb:$(this).find('input').is(":checked")}
              
              socket.emit('input_event', formdata);
            });

            $(document).on('click', '.card', function () {
            
              
              
              formdata={data: 'card_click',index: ($(this).index()),source:($(this).attr("id"))}

              if(performNativeJS("card_click",($(this).attr("id")),formdata)){   
                formdata["JSOutput"] = jsoutput;
                socket.emit('input_event', formdata);
              }
            });

            $(document).on('change','input:checkbox', function () {
            

             let formdata={data: 'checkbox',source:clickedID,sid:sid};
              var clickedID=this.id;
              jsonObj = [];
              item = {}
                
              item [clickedID] = this.checked;

              jsonObj.push(item);

              if(performNativeJS("checkbox_change",clickedID,formdata)){
                  jsonObj.push({"JSOutput":jsoutput});
                  jsonString = JSON.stringify(jsonObj);
                  formdata={data: 'button',values: jsonString,source:clickedID,sid:sid}
                  
                  socket.emit('input_event', formdata); 
                  
                  
              } 
             
            });

             $(document).on('change','select', function () {
            
              var selectedValue = this.selectedOptions[0].value;
              var selectedText  = this.selectedOptions[0].text;
              
              formdata={data: 'select_input',index: ($(this).index()),source:($(this).attr("id")),value:selectedValue}
              if($(this).attr("class")!="closedialogchange"){
              
              socket.emit('input_event', formdata);
              }
            });


            $(document).on('propertychange change keyup paste input', '.autotext', function () {
            
              
              
              formdata={data: 'text_input',index: ($(this).index()),source:($(this).attr("id")),value:($(this).val())}
                
              if(performNativeJS("text_input",($(this).attr("id")),formdata)){   
                formdata["JSOutput"] = jsoutput;
                socket.emit('input_event', formdata);
              }
            });
            

            $(document).on('click', 'button', function()
            {
            
              

              var clickedID=this.id

                

                if(clickedID.includes('maintab_')){
                    formdata={data: 'select_tab',source:clickedID.substring(8)}
                    
                    socket.emit('select_tab', formdata); 
                }
                else if(clickedID.includes('cardrow_')){
                    
                    formdata={data: 'card_event',source:clickedID }
                    
                    if(performNativeJS("card_event",($(this).attr("id")),formdata)){   
                    formdata["JSOutput"] = jsoutput;
                    socket.emit('input_event', formdata); 
                    }
                }
                else if(clickedID.includes('onResultPositive')||clickedID.includes('onResultNegative')){
                    //do nothing
                }
                else{

                

                jsonObj = [];
                  $("input").each(function() {

                var id = $(this).attr("id");
                var v = $(this).val();

                if($(this).attr('type')=='checkbox'){
                
                  
                v = $(this).is(":checked");

                };

                item = {}
                
                item [id] = v;

                jsonObj.push(item);
                });

                $("textarea").each(function() {

                var id = $(this).attr("id");
                var v = $(this).val();

                if(id==""||id==null||typeof id == 'undefined') {
                     id = $(this).parent().attr("id");
                     
                }

                item = {}
                
                item [id] = v;

                jsonObj.push(item);
                });

                
                


                
                if(performNativeJS("click",clickedID,formdata)){
                  jsonObj.push({"JSOutput":jsoutput});
                  jsonString = JSON.stringify(jsonObj);
                  formdata={data: 'button',values: jsonString,source:clickedID,sid:sid}
                  
                  socket.emit('input_event', formdata); 
                  }
                  
                }
            });


      

          
            

            $(document).on('click', "[id*='spanmaintab_']", function()
            {
              
                var clickedID=this.id
                
                formdata={data: 'ttt',source:clickedID.substring(12)}
                socket.emit('close_maintab', formdata);
                //document.getElementById(clickedID.substring(12)).setAttribute("style", "display:none")
                var element = document.getElementById(clickedID.substring(12));
                element.parentNode.removeChild(element);
                //document.getElementById("maintab_"+clickedID.substring(12)).setAttribute("style", "display:none")
                var element2 = document.getElementById("maintab_"+clickedID.substring(12));
                element2.parentNode.removeChild(element2);


            });

            $(document).on('click', "[id*='maintab_']", function()
            {
                socket.emit('input_event', {data:"tab_click",source: this.id });
             


            });


            
           

            $("[id*='spanmaintab_']").click(function() {
                
                var clickedID=this.id
                
                formdata={data: 'ttt',source:clickedID.substring(12)}
                socket.emit('close_maintab', formdata);
                //document.getElementById(clickedID.substring(12)).setAttribute("style", "display:none")
                var element = document.getElementById(clickedID.substring(12));
                element.parentNode.removeChild(element);
                //document.getElementById("maintab_"+clickedID.substring(12)).setAttribute("style", "display:none")
                var element2 = document.getElementById("maintab_"+clickedID.substring(12));
                element2.parentNode.removeChild(element2);
                
            });


             $("#sidenav").click(function(e) {
              
              var clickedOn = $(e.target);
              socket.emit('run_process', clickedOn.text());
            });

            socket.on('connect', function() {
              
                socket.emit('connect_event', {data: 'connected to the SocketServer...'});
            });

            async function UploadFile(data) 
{
 let formData = new FormData();
              let f = $('#'+data.file_id).prop('files')[0];   
                  
              formData.append("file", f);
             
              
              const ctrl = new AbortController()   
              setTimeout(() => ctrl.abort(), 10000);
              
              try {
                let r = await fetch('/upload_file?id='+data.file_id+'&sid='+socket.id, 
                  {method: "POST", body: formData, signal: ctrl.signal}); 
              
                  
                console.log('HTTP response code:',r.status); 
              } catch(e) {
                console.log('Some problem...:', e);
              }

}

            async function DownloadFile(data) 
{
              let formData = new FormData();
              
              const ctrl = new AbortController()   
              setTimeout(() => ctrl.abort(), 10000);
              
              try {
                let r = await fetch('/download_file?filename='+data.filename+'&sid='+socket.id, 
                  {method: "GET",  signal: ctrl.signal}); 
              
                  
                console.log('HTTP response code:',r.status); 
              } catch(e) {
                console.log('Some problem...:', e);
              }

}

          
          
          socket.on('upload_file', function (data) {

          if(!$('#'+data.file_id).val()){
                        alert("No file selected!");
                      
                        }else{

                      UploadFile(data)
                      }
                           
                      });

          socket.on('download_file', function (data) {
          
          DownloadFile(data)

      
                           
                      });          

            
                     

             socket.on('getcookie', function (data) {
                
              var r = Cookies.get();
              formdata={data: 'get_cookie',value:JSON.stringify(r)}
              socket.emit('cookie_event', formdata); 
                
               
            });

            socket.on('setcookie', function (data) {
                
              $.each(data, function(i, item) {
                  
                  Cookies.set(data[i].key, data[i].value, { expires:data[i].expires });
                }); 
                
               
            });          
            
            socket.on('setvalue', function (data) {
                
                $("#"+data.key).html(data.value);
                               
            });




            socket.on('setvalueedit', function (data) {
                
                $("#"+data.key).attr('value',data.value);
            });

            
            var mresult=0;
            function mouseDownEventHandler(id,e) {
             //e.preventDefault();
             //e.stopPropagation();

             var canvas = $("#"+id).get(0);
             var x = e.pageX - canvas.offsetLeft;
             var y = e.pageY - canvas.offsetTop;

             if(canvasevents){
                if(e.which == 1){
                 var point = {type:"mouseDown",x:x,y:y};
                 if(performNativeJS("mouseDown",id,point)){
                  
                 socket.emit('input_event', {data:"canvas_mouse_event",source: id,values:JSON.stringify(point)});

                 }
                }else{
                    var point = {type:"mouseDownOther",x:x,y:y,"button":e.which};
                    if(performNativeJS("mouseDownOther",id,point)){
                   socket.emit('input_event', {data:"canvas_mouse_event",source: id,values:JSON.stringify(point)});
                   }
                }
              }

             /*clicks++;

             if(clicks === 1) {

                timer = setTimeout(function() {
                
                mresult=1;

               
                clicks = 0; 
                

                if(e.which == 1){
                 var point = {type:"mouseDown",x:x,y:y};
                 if(performNativeJS("mouseDown",id,point)){
                  
                 socket.emit('input_event', {data:"canvas_mouse_event",source: id,values:JSON.stringify(point)});

                 }

                }else{
                    var point = {type:"mouseDownOther",x:x,y:y};
                    if(performNativeJS("mouseDownOther",id,point)){
                   socket.emit('input_event', {data:"canvas_mouse_event",source: id,values:JSON.stringify(point)});
                    }
                }
                         

            }, 200); 

            }
            
            else{
              
              clicks = 0;
             
              mresult=1;   
               var point = {type:"mouseDoubleClick",x:x,y:y};
               if(performNativeJS("mouseDoubleClick",id,point)){
               socket.emit('input_event', {data:"canvas_mouse_event",source: id,values:JSON.stringify(point)});
               }

            }*/

                         
             
           
             
            }

            

            function mouseMoveEventHandler(id,e) {
             var canvas = $("#"+id).get(0);
             var x = e.pageX - canvas.offsetLeft;
             var y = e.pageY - canvas.offsetTop;

             var point = {type:"mouseMove",x:x,y:y};
            
             if(performNativeJS("mouseMove",id,point)){
             if(canvasevents){
             socket.emit('input_event', {data:"canvas_mouse_event",source: id,values:JSON.stringify(point)});
             }
             }
             
            }

            function mouseUpEventHandler(id,e) {
            //if(mresult==1){
             mresult=0;
             var canvas = $("#"+id).get(0);
             var x = e.pageX - canvas.offsetLeft;
             var y = e.pageY - canvas.offsetTop;

             var point = {type:"mouseUp",x:x,y:y};
            
             if(performNativeJS("mouseUp",id,point)){
             socket.emit('input_event', {data:"canvas_mouse_event",source: id,values:JSON.stringify(point)});
             }

             //}
             
            }

            function onContextMenuHandler(e) {
             return false;
             
            }

  function canvas_arrow(context, fromx, fromy, tox, toy) {
  var headlen = 10; // length of head in pixels
  var dx = tox - fromx;
  var dy = toy - fromy;
  var angle = Math.atan2(dy, dx);
  context.moveTo(fromx, fromy);
  context.lineTo(tox, toy);
  context.lineTo(tox - headlen * Math.cos(angle - Math.PI / 6), toy - headlen * Math.sin(angle - Math.PI / 6));
  context.moveTo(tox, toy);
  context.lineTo(tox - headlen * Math.cos(angle + Math.PI / 6), toy - headlen * Math.sin(angle + Math.PI / 6));
}

socket.on('setcanvas', function (data) {
    "use strict";
    var canvas = $("#"+data.key).get(0);
    canvas.height = data.value.height;
    canvas.width = data.value.width;


    var context = canvas.getContext("2d");

    context.clearRect(0, 0, context.canvas.width, context.canvas.height);

    var draw_array = data.value.draw;


    draw_array.forEach(function(obj) { 
      if(obj.type=="cells"){
      
      var x=  obj.x;
      var y = obj.y;

      var tags = obj.tags;

      for(let i = 0; i < obj.col_count; i++){
      for(let j = 0; j < obj.row_count; j++){

      context.strokeStyle = "#ff0000";
      context.lineWidth = 1;

      context.beginPath();
      context.rect(x,y,obj.cell_size,obj.cell_size);
      context.stroke();
     
      var text = tags[i][j];
      context.font = "12px serif";
      var m = context.measureText(text);
      var mh = context.measureText("M");
     
      context.fillText(text, Math.round(x+obj.cell_size/2-m.width/2), Math.round(y+obj.cell_size/2+mh.width/2));
      y =y+obj.cell_size;
      }
      x =x+obj.cell_size;
      }

      }
      else if(obj.type=="cell"){
        

        context.beginPath();

        context.strokeStyle = "#000000";
        context.lineWidth = 1;
        if(obj.fill_color!=null)
        context.fillStyle = obj.fill_color;
        
        context.rect(obj.x1,obj.y1,obj.x2-obj.x1,obj.y2-obj.y1);
        context.stroke();
        if(obj.fill_color!=null)
        context.fill();
        
        context.fillStyle = "#000000";
        
        var text = obj.label;
        context.font = "12px serif";
        var m = context.measureText(text);
        var mh = context.measureText("M");
        
        context.fillText(text, Math.round(obj.x1+(obj.x2-obj.x1)/2-m.width/2), Math.round(obj.y1+(obj.y2-obj.y1)/2+mh.width/2));
        context.closePath();

        

     } 
     else if(obj.type=="line"){
        context.strokeStyle = obj.color;
        context.lineWidth = obj.strock_size;

        context.beginPath();
        context.moveTo(obj.x1,obj.y1);
        context.lineTo(obj.x2,obj.y2);
        
        context.stroke();
        
        context.closePath();

     } 
     else if(obj.type=="arrow"){
        context.beginPath();

        context.strokeStyle = obj.color;
        context.lineWidth = obj.strock_size;
        canvas_arrow(context, obj.x2,obj.y2,obj.x1,obj.y1);

        context.stroke();
        
        context.closePath();

     } 
     else if(obj.type=="rect"){
        context.beginPath();

        context.strokeStyle = obj.color;
        context.lineWidth = obj.strock_size;
        context.fillStyle = obj.fill_color;

        
        context.rect(obj.x1,obj.y1,obj.x2-obj.x1,obj.y2-obj.y1);
        context.stroke();
        context.fill();
        
        context.closePath();

     } else if(obj.type=="text"){
        context.fillStyle = obj.color;
        
        var text = obj.text;
        context.font = obj.size + "px serif";
        //var m = context.measureText(text);
        //var mh = context.measureText("M");
        
        context.fillText(text, obj.x, obj.y);

        context.closePath();
     } 


    });
    
     

   
                   
});
            

           socket.on('initstack', function (data) {
                hashMap = data.values;
                              
            });

            socket.on('initnativehandlers', function (data) {
                nativehandlers = data.handlers;
                              
            });

            socket.on('initcanvas', function (data) {
                "use strict";
                var canvas = $("#"+data.key).get(0);
                canvas.height = data.value.height;
                canvas.width = data.value.width;

                
                
                canvas.addEventListener("mousedown", mouseDownEventHandler.bind(null,  data.key), false);
                canvas.addEventListener('mousemove', mouseMoveEventHandler.bind(null,  data.key), false);
                canvas.addEventListener('mouseup', mouseUpEventHandler.bind(null,  data.key), false);

                canvasevents=true;
                

               
                               
            });

            socket.on('stopevents', function (data) {
                
            canvasevents=false;
               
                               
            });

            socket.on('startevents', function (data) {
                
            canvasevents=true;
               
                               
            });

            socket.on('setvisible', function (data) {
                
                $("#"+data.key).css('visibility',data.value1);
                $("#"+data.key).css('display',data.value2);
            });

            socket.on('blocktabs', function (data) {
                
                $("#maintabs").css('pointer-events','none');
                
            });

            socket.on('unblocktabs', function (data) {
                
                $("#maintabs").css('pointer-events','auto');
                
            });


            socket.on('setvaluepulse', function (data) {
               
                $("#"+data.key).html(data.value);
                var animTime = 200;
 	              //$("#"+data.key).addClass('alert', animTime).removeClass('alert', animTime);
                //$("#"+data.key).css('background-color', '#f44336');
                //$("#"+data.key).animate({ "font-size": "120%" }, 1000).animate({ "font-size": "100%" }, 1000);
                $("#"+data.key).animate({ "backgroundColor": "#f44336" }, 1000).animate({ "backgroundColor": "#ffffff" }, 1000);
            });

            socket.on('setvaluehtml', function (data) {
              
              
              $("#"+data.key).html(data.value);
                
            });

            socket.on('setmenulisteners', function (data) {
            var dropdown = document.getElementsByClassName("dropdown-btn");
            var i;

            for (i = 0; i < dropdown.length; i++) {
              dropdown[i].addEventListener("click", function() {
                this.classList.toggle("active");
                var dropdownContent = this.nextElementSibling;
                if (dropdownContent.style.display === "block") {
                  dropdownContent.style.display = "none";
                } else {
                  dropdownContent.style.display = "block";
                }
              });
            }
            
            });

            socket.on('add_html', function (data) {
                 
                 //document.getElementById(data.id).innerHTML += data.code;
                 $('#'+data.id).append(data.code);

            });

            socket.on('close_tab', function (data) {

                
                                
                var element = document.getElementById(data.tabid);
                if(element!=null){
                element.parentNode.removeChild(element);}
                
                var element2 = document.getElementById(data.buttonid);
                if(element2!=null){
                element2.parentNode.removeChild(element2);
                  }


            });

            

             
           socket.on('run_datatable', function (data) {
            
           
           
            //$('#'+data.id).DataTable();

            $('#'+data.id).DataTable({
                
                "language": {
                    "search": "Искать",
                    "lengthMenu": "Показать _MENU_ строк",
                    "zeroRecords": "Нет строк",
                    "info": "Показано _PAGE_ из _PAGES_",
                    "infoFiltered": "(отобрано from _MAX_ всего записей)",
                    "paginate": {
                    "first":      "Первые",
                    "last":       "Последние",
                    "next":       "Следующий",
                    "previous":   "Предыдущий"
                    }

                }
            });
          
           
           
           
           });

           
          socket.on('eval_js', function (data) {
                 var script =  data.script;
                 var hashMap = data.hashMap;
                 var id_handler = data.id;

                 try {

                      var F=new Function ('hashMap',script);
                      res = F(hashMap);
                      socket.emit('js_result', {code:1,id: id_handler,value:res});

                 } catch (err) { 
                      
                      socket.emit('js_result', {code:-1,id: id_handler,value:String(err)});

                 }


                 
            }); 
          
          socket.on('notification', function (data) {
                
                if (!("Notification" in window)) {
    
                   
                } else if (Notification.permission === "granted") {
    
                    const notification = new Notification(data.text);
    
                } else if (Notification.permission !== "denied") {
    
                  Notification.requestPermission().then((permission) => {
      
                if (permission === "granted") {
                    const notification = new Notification(data.text);
        
              }
    });
  }

            });  
            
             socket.on('error', function (data) {
                  
                 document.getElementById("errorModal").style.display = "block";
                 document.getElementById("errorbody").innerHTML=data.code;


                 $("#toastModal").delay(3200).fadeOut(300);
            });

            socket.on('toast', function (data) {
                 
                 //$("#maintop").append(data.code);

                //var modal = document.getElementById("toastModal");
                 document.getElementById("toastModal").style.display = "block";
                 document.getElementById("toastbody").innerHTML=data.code;


                 $("#toastModal").delay(3200).fadeOut(300);
            });

            socket.on('beep', function (data) {
              
              var snd = new Audio("data:audio/wav;base64,//uQRAAAAWMSLwUIYAAsYkXgoQwAEaYLWfkWgAI0wWs/ItAAAGDgYtAgAyN+QWaAAihwMWm4G8QQRDiMcCBcH3Cc+CDv/7xA4Tvh9Rz/y8QADBwMWgQAZG/ILNAARQ4GLTcDeIIIhxGOBAuD7hOfBB3/94gcJ3w+o5/5eIAIAAAVwWgQAVQ2ORaIQwEMAJiDg95G4nQL7mQVWI6GwRcfsZAcsKkJvxgxEjzFUgfHoSQ9Qq7KNwqHwuB13MA4a1q/DmBrHgPcmjiGoh//EwC5nGPEmS4RcfkVKOhJf+WOgoxJclFz3kgn//dBA+ya1GhurNn8zb//9NNutNuhz31f////9vt///z+IdAEAAAK4LQIAKobHItEIYCGAExBwe8jcToF9zIKrEdDYIuP2MgOWFSE34wYiR5iqQPj0JIeoVdlG4VD4XA67mAcNa1fhzA1jwHuTRxDUQ//iYBczjHiTJcIuPyKlHQkv/LHQUYkuSi57yQT//uggfZNajQ3Vmz+Zt//+mm3Wm3Q576v////+32///5/EOgAAADVghQAAAAA//uQZAUAB1WI0PZugAAAAAoQwAAAEk3nRd2qAAAAACiDgAAAAAAABCqEEQRLCgwpBGMlJkIz8jKhGvj4k6jzRnqasNKIeoh5gI7BJaC1A1AoNBjJgbyApVS4IDlZgDU5WUAxEKDNmmALHzZp0Fkz1FMTmGFl1FMEyodIavcCAUHDWrKAIA4aa2oCgILEBupZgHvAhEBcZ6joQBxS76AgccrFlczBvKLC0QI2cBoCFvfTDAo7eoOQInqDPBtvrDEZBNYN5xwNwxQRfw8ZQ5wQVLvO8OYU+mHvFLlDh05Mdg7BT6YrRPpCBznMB2r//xKJjyyOh+cImr2/4doscwD6neZjuZR4AgAABYAAAABy1xcdQtxYBYYZdifkUDgzzXaXn98Z0oi9ILU5mBjFANmRwlVJ3/6jYDAmxaiDG3/6xjQQCCKkRb/6kg/wW+kSJ5//rLobkLSiKmqP/0ikJuDaSaSf/6JiLYLEYnW/+kXg1WRVJL/9EmQ1YZIsv/6Qzwy5qk7/+tEU0nkls3/zIUMPKNX/6yZLf+kFgAfgGyLFAUwY//uQZAUABcd5UiNPVXAAAApAAAAAE0VZQKw9ISAAACgAAAAAVQIygIElVrFkBS+Jhi+EAuu+lKAkYUEIsmEAEoMeDmCETMvfSHTGkF5RWH7kz/ESHWPAq/kcCRhqBtMdokPdM7vil7RG98A2sc7zO6ZvTdM7pmOUAZTnJW+NXxqmd41dqJ6mLTXxrPpnV8avaIf5SvL7pndPvPpndJR9Kuu8fePvuiuhorgWjp7Mf/PRjxcFCPDkW31srioCExivv9lcwKEaHsf/7ow2Fl1T/9RkXgEhYElAoCLFtMArxwivDJJ+bR1HTKJdlEoTELCIqgEwVGSQ+hIm0NbK8WXcTEI0UPoa2NbG4y2K00JEWbZavJXkYaqo9CRHS55FcZTjKEk3NKoCYUnSQ0rWxrZbFKbKIhOKPZe1cJKzZSaQrIyULHDZmV5K4xySsDRKWOruanGtjLJXFEmwaIbDLX0hIPBUQPVFVkQkDoUNfSoDgQGKPekoxeGzA4DUvnn4bxzcZrtJyipKfPNy5w+9lnXwgqsiyHNeSVpemw4bWb9psYeq//uQZBoABQt4yMVxYAIAAAkQoAAAHvYpL5m6AAgAACXDAAAAD59jblTirQe9upFsmZbpMudy7Lz1X1DYsxOOSWpfPqNX2WqktK0DMvuGwlbNj44TleLPQ+Gsfb+GOWOKJoIrWb3cIMeeON6lz2umTqMXV8Mj30yWPpjoSa9ujK8SyeJP5y5mOW1D6hvLepeveEAEDo0mgCRClOEgANv3B9a6fikgUSu/DmAMATrGx7nng5p5iimPNZsfQLYB2sDLIkzRKZOHGAaUyDcpFBSLG9MCQALgAIgQs2YunOszLSAyQYPVC2YdGGeHD2dTdJk1pAHGAWDjnkcLKFymS3RQZTInzySoBwMG0QueC3gMsCEYxUqlrcxK6k1LQQcsmyYeQPdC2YfuGPASCBkcVMQQqpVJshui1tkXQJQV0OXGAZMXSOEEBRirXbVRQW7ugq7IM7rPWSZyDlM3IuNEkxzCOJ0ny2ThNkyRai1b6ev//3dzNGzNb//4uAvHT5sURcZCFcuKLhOFs8mLAAEAt4UWAAIABAAAAAB4qbHo0tIjVkUU//uQZAwABfSFz3ZqQAAAAAngwAAAE1HjMp2qAAAAACZDgAAAD5UkTE1UgZEUExqYynN1qZvqIOREEFmBcJQkwdxiFtw0qEOkGYfRDifBui9MQg4QAHAqWtAWHoCxu1Yf4VfWLPIM2mHDFsbQEVGwyqQoQcwnfHeIkNt9YnkiaS1oizycqJrx4KOQjahZxWbcZgztj2c49nKmkId44S71j0c8eV9yDK6uPRzx5X18eDvjvQ6yKo9ZSS6l//8elePK/Lf//IInrOF/FvDoADYAGBMGb7FtErm5MXMlmPAJQVgWta7Zx2go+8xJ0UiCb8LHHdftWyLJE0QIAIsI+UbXu67dZMjmgDGCGl1H+vpF4NSDckSIkk7Vd+sxEhBQMRU8j/12UIRhzSaUdQ+rQU5kGeFxm+hb1oh6pWWmv3uvmReDl0UnvtapVaIzo1jZbf/pD6ElLqSX+rUmOQNpJFa/r+sa4e/pBlAABoAAAAA3CUgShLdGIxsY7AUABPRrgCABdDuQ5GC7DqPQCgbbJUAoRSUj+NIEig0YfyWUho1VBBBA//uQZB4ABZx5zfMakeAAAAmwAAAAF5F3P0w9GtAAACfAAAAAwLhMDmAYWMgVEG1U0FIGCBgXBXAtfMH10000EEEEEECUBYln03TTTdNBDZopopYvrTTdNa325mImNg3TTPV9q3pmY0xoO6bv3r00y+IDGid/9aaaZTGMuj9mpu9Mpio1dXrr5HERTZSmqU36A3CumzN/9Robv/Xx4v9ijkSRSNLQhAWumap82WRSBUqXStV/YcS+XVLnSS+WLDroqArFkMEsAS+eWmrUzrO0oEmE40RlMZ5+ODIkAyKAGUwZ3mVKmcamcJnMW26MRPgUw6j+LkhyHGVGYjSUUKNpuJUQoOIAyDvEyG8S5yfK6dhZc0Tx1KI/gviKL6qvvFs1+bWtaz58uUNnryq6kt5RzOCkPWlVqVX2a/EEBUdU1KrXLf40GoiiFXK///qpoiDXrOgqDR38JB0bw7SoL+ZB9o1RCkQjQ2CBYZKd/+VJxZRRZlqSkKiws0WFxUyCwsKiMy7hUVFhIaCrNQsKkTIsLivwKKigsj8XYlwt/WKi2N4d//uQRCSAAjURNIHpMZBGYiaQPSYyAAABLAAAAAAAACWAAAAApUF/Mg+0aohSIRobBAsMlO//Kk4soosy1JSFRYWaLC4qZBYWFRGZdwqKiwkNBVmoWFSJkWFxX4FFRQWR+LsS4W/rFRb/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////VEFHAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAU291bmRib3kuZGUAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAMjAwNGh0dHA6Ly93d3cuc291bmRib3kuZGUAAAAAAAAAACU=");  
              snd.play();
                 
            });

            socket.on('read_clipboard', function (data) {
            
              
            navigator.permissions.query({ name: 'clipboard-read' })
    .then((result) => {
        
        if (result.state == 'granted' || result.state == 'prompt') {
            
            navigator.clipboard.readText().then(
  clipText => socket.emit('input_event', {data:"clipboard_result",source: "",value:clipText}));
        }
    });

              
                
            });

            socket.on('write_clipboard', function (data) {
             
              if (navigator.clipboard && window.isSecureContext) {
              navigator.clipboard.writeText(data.value).then(function() {
                console.log('Async: Copying to clipboard was successful!');
              }, function(err) {
                console.error('Async: Could not copy text: ', err);
              });
              }
              else {
                  
                  const textArea = document.createElement("textarea");
                  textArea.value = data.value;
                      
                  
                  textArea.style.position = "absolute";
                  textArea.style.left = "-999999px";
                      
                  document.body.prepend(textArea);
                  textArea.select();

                  try {
                      document.execCommand('copy');
                  } catch (error) {
                      console.error(error);
                  } finally {
                      textArea.remove();
                  }
              }
                
            });

            socket.on('show_dialog', function (data) {
                  
                
                 
                 //$("#dialogModal").modal("show");

                const modal = document.querySelector("dialog")

                
                modal.showModal();
               

                const closeBtns = document.getElementsByClassName("closedialog");

                for (btn of closeBtns) {
                btn.addEventListener("click", dialogbutton)
                }

                const changeBtns = document.getElementsByClassName("closedialogchange");

                for (btn of changeBtns) {
                btn.addEventListener("change", dialogbutton)
                }

                async function readFileAsDataURL(file) {
                    let result_base64 = await new Promise((resolve) => {
                        let fileReader = new FileReader();
                        fileReader.onload = (e) => resolve(fileReader.result.split(',')[1]);
                        fileReader.readAsDataURL(file);
                    });

                    console.log(result_base64); // aGV5IHRoZXJl...

                    return result_base64;
                }

                function dialogbutton(event) {
                
                    
                
                    jsonObj = [];
                    $("input", $("#contentModalDialog")).each(function() {
                    

                    var id = $(this).attr("id");
                    var v = $(this).val();

                    if($(this).attr('type')=='checkbox'){
                      
                    v = $(this).is(":checked");

                    };

                   

                    item = {}
                    
                    item [id] = v;

                    jsonObj.push(item);
                    });

                    $("textarea", $("#contentModalDialog")).each(function() {

                    var id = $(this).attr("id");
                   
                    var v = $(this).val();
                    
                    if(id==""||id==null||typeof id == 'undefined') {
                     id = $(this).parent().attr("id");
                     
                    }

                    item = {}
                    
                    item [id] = v;

                    jsonObj.push(item);
                    });

                    $("select", $("#contentModalDialog")).each(function() {

                    var id = $(this).attr("id");
                    var v = $(this).val();

                    item = {}
                    
                    item [id] = v;

                    jsonObj.push(item);
                    });
                    

                    

                    $("input", $("#contentModalDialog")).each(function() {
                    

                    var id = $(this).attr("id");
                    var v = $(this).val();

                    

                    if($(this).attr('type')=='file'){
                      
                      const  file = $('#'+id).prop('files')[0];
                      

                      if (file) {
                        readFileAsDataURL(file).then(dataURL => {
                        
                        item = {}
                        
                        item ["base64"] =dataURL
                        
                        jsonObj.push(item);
                        if(performNativeJS("dialog_result",event.target.id,jsonObj)){
                        jsonObj.push({"JSOutput":jsoutput});
                        
                        jsonString = JSON.stringify(jsonObj);
                        socket.emit('input_event', {data:"dialog_result",source: event.target.id,values:jsonString});
                        }
                        });
                        
                      }

                       item = {}
                    
                       item [id] = v;

                       jsonObj.push(item);


                    }

                   
                    });
                    

                    


                    
              
                    if(performNativeJS("dialog_result",event.target.id,jsonObj)){
                    jsonObj.push({"JSOutput":jsoutput});
                    jsonString = JSON.stringify(jsonObj);
                    socket.emit('input_event', {data:"dialog_result",source: event.target.id,values:jsonString});
                    }
                    modal.close();
                }
                
            });

            socket.on('show_modal', function (data) {
                  
                
                 
                 //$("#dialogModal").modal("show");

                const modal = document.querySelector("dialog")

                
                modal.showModal();
               

                const closeBtns = document.getElementsByClassName("closedialog");

                for (btn of closeBtns) {
                btn.addEventListener("click", dialogbutton)
                }

                function dialogbutton(event) {
                    

                     jsonObj = [];
                  $("#contentModal :input").each(function() {

                var id = $(this).attr("id");
                var v = $(this).val();

                if($(this).attr('type')=='checkbox'){
                  
                v = $(this).is(":checked");
                };

                item = {};
                
                item [id] = v;

                jsonObj.push(item);
                });

                $("#contentModal textarea").each(function() {

                var id = $(this).attr("id");
                var v = $(this).val();

                item = {}
                
                item [id] = v;

                jsonObj.push(item);
                });

                

                jsonString = JSON.stringify(jsonObj);
               


                    socket.emit('input_event', {data:"edittable_result",source: event.target.id,values: jsonString,table_id:data.table_id,selected_line_id:data.selected_line_id });
                    modal.close();
                }
                
            });

            socket.on('click_button', function (data) {
                 var element = document.getElementById(data.id)
                 if (element != null){
                 element.click();}
                 
            });

            socket.on('add_html_body', function (data) {
                
                 $('body').append(data.code);
            });

            socket.on('reload', function (data) {
                location.reload();
                //location.href += "?login"; 
            });

            
            $('form#emit').submit(function(event) {
                socket.emit('input_event', {data: $('#emit_data').val()});
                return false;
            });
           
            $('form#disconnect').submit(function(event) {
                socket.emit('disconnect_request');
                return false;
            });
        });
    </script>

    
   
   <style>
body {font-family: Arial;}

button {
  background: #ededed;
  border: 1px solid #ccc;
  padding: 5px 10px;
  cursor: pointer;
}

button:active {
  background: #e5e5e5;
  -webkit-box-shadow: inset 0px 0px 5px #c1c1c1;
     -moz-box-shadow: inset 0px 0px 5px #c1c1c1;
          box-shadow: inset 0px 0px 5px #c1c1c1;
   outline: none;
}

/* The Modal (background) */
.toastmodal {
  display: none; 
  position: fixed;
  z-index: 1; /* Sit on top */
  left: 0;
  top: 0;


  width: 100%; 
  height: 100%; /
  overflow: auto; 
  background-color: rgb(0,0,0); 
  background-color: rgba(0,0,0,0.4); 
  -webkit-animation-name: fadeIn; 
  -webkit-animation-duration: 0.4s;
  animation-name: fadeIn;
  animation-duration: 0.4s
}

/* Modal Content */
.toastmodal-content {
 
  position: fixed;
  bottom: 0;
  background-color: #fefefe;
  width: 100%;
  -webkit-animation-name: slideIn;
  -webkit-animation-duration: 0.4s;
  animation-name: slideIn;
  animation-duration: 0.4s
}

/*Table highlight*/
.highlight {
   background-color: #a8cb17 !important;
}

/* The Close Button */
.toastclose {
  color: white;
  float: right;
  font-size: 28px;
  font-weight: bold;
}

.toastclose:hover,
.toastclose:focus {
  color: #000;
  text-decoration: none;
  cursor: pointer;
}

.toastmodal-header {
  padding: 1px;
  
  background-color: #124526;
  color: white;
}


/*error message*/
.errormodal {
  display: none; 
  position: fixed; 
  z-index: 1; 
  
  left: 0;
  top: 0;
  width: 100%; 
  height: 100%; 
  overflow: auto; 
  background-color: rgb(0,0,0); 
  background-color: rgba(0,0,0,0.4); 
  -webkit-animation-name: fadeIn; 
  -webkit-animation-duration: 0.4s;
  animation-name: fadeIn;
  animation-duration: 0.4s
}



/* Modal Content */
.errormodal-content {
  position: fixed;
  
  bottom: 0;
  background-color: #fefefe;
  width: 100%;
  -webkit-animation-name: slideIn;
  -webkit-animation-duration: 0.4s;
  animation-name: slideIn;
  animation-duration: 0.4s
}

/* The Close Button */
.errorclose {
  color: white;
  float: right;
  font-size: 28px;
  font-weight: bold;
}

.errorclose:hover,
.errorclose:focus {
  color: #000;
  text-decoration: none;
  cursor: pointer;
}

.errormodal-header {
  padding: 2px 2px;
  background-color: #f54242;
  color: white;
}




.dialogmodal-header {
  padding: 2px;
  background-color: #2c569c;
  color: white;
  font-size: 18px;
}



.modal-body {padding: 2px 16px;}


/* Add Animation */
@-webkit-keyframes slideIn {
  from {bottom: -300px; opacity: 0} 
  to {bottom: 0; opacity: 1}
}

@keyframes slideIn {
  from {bottom: -300px; opacity: 0}
  to {bottom: 0; opacity: 1}
}

@-webkit-keyframes fadeIn {
  from {opacity: 0} 
  to {opacity: 1}
}

@keyframes fadeIn {
  from {opacity: 0} 
  to {opacity: 1}
}


@media (prefers-reduced-motion: reduce) {
    .fade {
        transition: none;
    }
}


.alert {
  padding: 20px;
  background-color: #f44336;
  color: white;
}

.pulse {
        background-color: #AD310B;     
    }

.closedialog {
  margin-left: 2px;
  color: black;
  font-weight: bold;
  float: right;
  font-size: 18px;
 
}

.closebtn {
  margin-left: 15px;
  color: white;
  font-weight: bold;
  float: right;
  font-size: 22px;
  line-height: 20px;
  cursor: pointer;
  transition: 0.3s;
}

.closebtn:hover {
  color: black;
}

.autotext {
  
  background-color: #FFFACD;
}

.tab {
  overflow: hidden;
  border: 1px solid #ccc;
  background-color: #f1f1f1;
}


.tab button {
  background-color: inherit;
  float: left;
  border: none;
  outline: none;
  cursor: pointer;
  padding: 14px 16px;
  transition: 0.3s;
  font-size: 17px;
}


.tab button:hover {
  background-color: #ddd;
}


.tab button.active {
   background-color: #696969;
  color: white;
}


.tabcontent {
  display: none;
  padding: 2px 12px;
  border: 1px solid #ccc;
  border-top: none;
  
  
  
}

.tabcontentlayout {
  display: none;
  padding: 1px 10px;
  border: 1px solid #ccc;
  border-top: none;
  
}

.topright {
float: right;  
  cursor: pointer;
  font-size: 28px;
}

.topright:hover {color: red;}

.shadow-1:before {
  content: "";
  position: absolute;
  left: 0;
  right: 0;
  top: 0;
  bottom: 0;
  width: inherit;
  height: inherit;
  z-index: -2;
  box-sizing: border-box;
  box-shadow: 0 2px 5px 0 rgba(0, 0, 0, 0.13);
}

.shadow-1:after {
  content: "";
  position: absolute;
  left: 0;
  right: 0;
  top: 0;
  bottom: 0;
  width: inherit;
  height: inherit;
  z-index: -2;
  box-sizing: border-box;
  box-shadow: 0 2px 10px 0 rgba(0, 0, 0, 0.08);
}
.card {
  position: relative;
  
  background: #fcfcfc;
  margin: 20px 40px;
  transition: 0.4s all;
}

</style>


    <style>
    .container-horizontal {  
    padding: 1px;
    display: flex;
    display: -webkit-flex;
    flex-direction:row;
    flex: 1 1 auto;
 

    margin: 5px;
    }

    .container-vertical{  
    padding: 1px;
    display: flex;
    display: -webkit-flex;
    flex: 1 1 auto;
    

    flex-direction:column;
    margin: 5px;
    }

  .button2 {
  background-color: white;
  color: black;
  border: 2px solid #008CBA;
  }

    </style>

  
  <style>
  /*боковое меню процессов*/


/* Fixed sidenav, full height */
.sidenav {
  height: 100%;
  width: 200px;
  position: fixed;
  z-index: 1;
  top: 0;
  left: 0;
  background-color: #111;
  overflow-x: hidden;
  padding-top: 20px;
}


.sidenav a, .dropdown-btn {
  padding: 6px 8px 6px 16px;
  text-decoration: none;
  font-size: 20px;
  color: #818181;
  display: block;
  border: none;
  background: none;
  width: 100%;
  text-align: left;
  cursor: pointer;
  outline: none;
}

/* On mouse-over */
.sidenav a:hover, .dropdown-btn:hover {
  color: #f1f1f1;
}

div.content {
  margin-left: 200px;
  padding: 1px 16px;
  height: 1000px;
}

@media screen and (max-width: 700px) {
  .sidenav {
    width: 100%;
    height: auto;
    position: relative;
  }
  .sidenav a {float: left;}
  div.main {margin-left: 0;}
}

@media screen and (max-width: 400px) {
  .sidenav a {
    text-align: center;
    float: none;
  }
}


/* Main content */
.main {
  margin-left: 200px; 
  font-size: 18px; 
  padding: 0px 10px;

}

/* Add an active class to the active dropdown button */
.active {
  background-color: green;
  color: white;
}

/* Dropdown container (hidden by default). Optional: add a lighter background color and some left padding to change the design of the dropdown content */
.dropdown-container {
  display: none;
  background-color: #262626;
  padding-left: 8px;
}

/* Optional: Style the caret down icon */
.fa-caret-down {
  float: right;
  padding-right: 8px;
}

/* Some media queries for responsiveness */
@media screen and (max-height: 450px) {
  .sidenav {padding-top: 15px;}
  .sidenav a {font-size: 18px;}
}
</style>



    </head>



    <body>

    <div class="sidenav" id="sidenav">



</div>

<div class="main" id="maincontainer">

  <div class="tab" id="maintabs">   
    </div>
<div  id="maintop">
</div>
    




 <div id="modaldialog">

 </div>



</div>

    
  <!-- toast -->
<div id="toastModal" class="toastmodal">

  
  <div class="toastmodal-content">
    <div class="toastmodal-header">
      <span class="toastclose">&times;</span>
      <h5 style="padding-left: 1%;">Информация</h5>
    </div>
    <div class="toastmodal-body">
      <p style="padding-left: 1%;" id="toastbody"/>
      <p/>
    </div>
    
  </div>

</div>

 <!-- error -->
<div id="errorModal" class="errormodal">

  
  <div class="errormodal-content">
    <div class="errormodal-header">
      <span class="errorclose">&times;</span>
      <h5 style="padding-left: 1%;">Ошибка</h5>
    </div>
    <div class="errormodal-body">
      <p style="padding-left: 1%;" id="errorbody"/>
      <p/>
    </div>
    
  </div>

</div>



 

    </body>

    
    <script>
function openTab(evt, tabName) {
  var i, tabcontent, tablinks;
  tabcontent = document.getElementsByClassName("tabcontent");
  for (i = 0; i < tabcontent.length; i++) {
    tabcontent[i].style.display = "none";
  }
  tablinks = document.getElementsByClassName("tablinks");
  for (i = 0; i < tablinks.length; i++) {
    tablinks[i].className = tablinks[i].className.replace(" active", "");
  }
  document.getElementById(tabName).style.display = "block";
  evt.currentTarget.className += " active";
}
</script>

    <script>
function openTabLayout(tabsid,evt, tabName) {
  
  var i, tabcontent, tablinks;
  tabcontent = document.getElementById(tabsid).parentElement.getElementsByClassName("tabcontentlayout");
  for (i = 0; i < tabcontent.length; i++) {
   
    tabcontent[i].style.display = "none";
  }
  tablinks = document.getElementById(tabsid).parentElement.getElementsByClassName("tablinks");
  for (i = 0; i < tablinks.length; i++) {
   
    tablinks[i].className = tablinks[i].className.replace(" active", "");
  }
  
  document.getElementById(tabName).style.display = "block";
  evt.currentTarget.className += " active";
}
</script>

<script>
function openProcess(strId) {
    
    //alert(strId);
}

</script>





<script>
     var modal = document.getElementById("toastModal");

    var span = document.getElementsByClassName("toastclose")[0];


    span.onclick = function() {
      modal.style.display = "none";
    }


      window.onclick = function(event) {
      if (event.target == modal) {
        modal.style.display = "none";
      }
    }

    </script>

<script>
    var modal = document.getElementById("errorModal");
     
    var span = document.getElementsByClassName("errorclose")[0];

    span.onclick = function() {
      modal.style.display = "none";
    }

      window.onclick = function(event) {
      if (event.target == modal) {
        modal.style.display = "none";
      }
    }

    </script>


    </html>"""

    soup = bs4.BeautifulSoup(source,features="lxml")

    nav= soup.find(id="sidenav")
    if not nav==None and "ClientConfiguration" in self.configuration:
      
      if not self.isreload:
        for   process in self.configuration['ClientConfiguration']['Processes']:
            if str(process.get("login_screen",'')).lower()=="true":
              new_menu  = soup.new_tag("a",   href="javascript:void(0)")
              new_menu.string=process.get("ProcessName")
              nav.append(new_menu)

              self.islogin=True
              self.loginprocess=process.get("ProcessName")

              tabid = str(uuid.uuid4().hex) 
              self.current_tab_id=tabid
              self.new_screen_tab(self.configuration,self.loginprocess,'',soup,tabid)

              break

      if not self.islogin or self.isreload:
        #TODO ненадежно при большом количестве подключений
        Simple.isreload=False

        menustr=self.configuration['ClientConfiguration'].get("MenuWebTemplate")  
        #menustr =[{"caption":"Раздел 1","elements":[{"caption":"экраны","process":"экран"},{"caption":"список карточек","process":"список карточек"}]},{"caption":"Прочее","elements":[{"caption":"Асинхрон","process":"Асинхрон"}]}]

        self.make_menu(soup,nav,menustr)
      
      if not self.loginreload:    
        if "HTMLHead" in self.configuration['ClientConfiguration']:
          nw_st = soup.new_tag("script")
          string = base64.b64decode(self.configuration['ClientConfiguration']["HTMLHead"]).decode("utf-8")
          
          soup.head.append(string)
           
        if "StyleTemplates" in self.configuration['ClientConfiguration']:
          for   style in self.configuration['ClientConfiguration']['StyleTemplates']:
            if style.get("use_as_class") == True:
              nw_st = soup.new_tag("style")
              nw_st.string="."+style.get("name","noname")+"{"+style.get("row","")+"}"
              soup.head.append(nw_st)
       
      

      if 'OpenScreen' in self.hashMap:
        tabparameters = json.loads(self.hashMap.get('OpenScreen'))
        self.hashMap.pop('OpenScreen',None) 
        tabid = str(uuid.uuid4().hex)   
        self.current_tab_id=tabid
        self.new_screen_tab(self.configuration,tabparameters['process'],tabparameters['screen'],soup,tabid)
    else:
      main= soup.find(id="maincontainer")
      new_tag = soup.new_tag("h1")
      new_tag.string="Добро пожаловать в Simple!"
      main.append(new_tag)
      new_tag = soup.new_tag("br")
   
      main.append(new_tag)
      new_tag = soup.new_tag("h2")
      new_tag.string="На сервере отсутствует конфигурация. Ее следут загрузить. "
      main.append(new_tag)
      

    source = soup.prettify()
    
  


    items = []
    # items.append(dict(npp="№ п/п", name="Наименование товара",price="Цена"))
    # for i in range(1, 11):
    #     i = str(i)
    #     item = dict(npp=i, name="Товар "+i,price=str(random.randint(10, 10000)))
    #     items.append(item)

    #htmlstring = render_template_string(source,docdata=docdata)

    #t = Template(htmlstring)
    #res = t.render(items=items,docdata=docdata)

    htmlsource = html.unescape(source)

    if "HTMLdocument_ready" in self.configuration['ClientConfiguration']:
      string = base64.b64decode(self.configuration['ClientConfiguration']["HTMLdocument_ready"]).decode("utf-8")
      htmlsource  = htmlsource.replace("//#HTMLdocument_ready",string+";")

    return htmlsource
  
  def make_menu(self,soup,nav, menustr):
    if menustr==None:
      menustr=""

    if len(menustr)>0:
          menutemplate=json.loads(menustr)
          self.menutemplate=[]
          for top in menutemplate:
            new_toplevel  = soup.new_tag("button",    **{'class':'dropdown-btn'})
            new_toplevel.string = top.get("caption")
            new_i = soup.new_tag("i",    **{'class':'fa fa-caret-down'})
            new_toplevel.append(new_i)  
            nav.append(new_toplevel)

            new_topleveldiv  = soup.new_tag("div",    **{'class':'dropdown-container'})

            for el in top['elements']:
              new_menu  = soup.new_tag("a",   href="javascript:void(0)")
              new_menu.string=el.get("caption")
              new_topleveldiv.append(new_menu)
              self.menutemplate.append(el)

            nav.append(new_topleveldiv)   
        
    else:

          for   process in self.configuration['ClientConfiguration']['Processes']:
            if process.get("type",'')=="Process":
              hidden=False
              if 'hidden' in process:
                if process['hidden']==True or str(process['hidden'])=="true":
                  hidden=True

              if not hidden:
                new_menu  = soup.new_tag("a",   href="javascript:void(0)")
                new_menu.string=process.get("ProcessName")
                nav.append(new_menu)

  def new_screen_tab(self,configuration,processname,screenname,soup,tabid,title=None,no_close=False):

   openclick ="openTab(event, '"+tabid+"')"
   newTab = soup.new_tag("button", id="maintab_"+tabid,  **{'class':'tablinks'}, onclick=openclick)
   if title==None:
    newTab.string=processname
   else:
    newTab.string=title


   maintabs = soup.find(id="maintabs")
   if not maintabs==None:
    maintabs.append(newTab)

   new_tab_content =soup.new_tag("div", id=tabid,  **{'class':'tabcontent'})


   if not no_close: 
    new_container = soup.new_tag("div", style="display: flex;flex:auto;flex-direction:column;align-items:flex-end;" )
    new_span = soup.new_tag("span",id="spanmaintab_"+tabid,  **{'class':'topright'} )
    new_span.string=html.unescape('&#9746;')
    new_container.append(new_span)

    new_tab_content.append(new_container)

   new_element = soup.new_tag("div", id="root_"+tabid,  **{'class':'container-vertical'},style="height:100%;width:100%;")

  
 

   self.process = get_process(configuration,processname)
   self.screen= get_screen(self.process,screenname)

   self.tabs[tabid]=self.screen

   

   self.RunEvent("onStart") 
  

   layots = self.get_layouts(soup,self.screen,0)
   new_element.append(layots)

   new_tab_content.append(new_element)

   main= soup.find(id="maincontainer")
   if not main==None:
     main.append(new_tab_content)


   new_tag = soup.new_tag("script" )
   new_tag.string = 'document.getElementById("'+"maintab_"+tabid+'").click();'
   soup.append(new_tag)

   

   return newTab,new_tab_content  
       
  def read_globals(self):
     for k,v in self.hashMapGlobals.items():
        self.hashMap[k]=v
  
  def write_globals(self):
     for k,v in self.hashMap.items():
        if k[0]=="_":
          self.hashMapGlobals[k]=v      

  def on_launch(self,data):
      
      jhandlers = []
      if 'CommonHandlers' in self.configuration['ClientConfiguration']:
        for h in self.configuration['ClientConfiguration']['CommonHandlers']:
           if h["event"] == "onWebEvent":
              jhandlers.append(h)
        if len(jhandlers)>0:      
          self.socket_.emit('initnativehandlers', {"handlers":jhandlers},room=self.sid,namespace='/'+SOCKET_NAMESPACE)
      
      self.hashMap['listener']='onLaunch'
      self.RunEvent("onLaunch",None,True)

  def select_tab(self,data):
    
    if  isinstance(data,dict):
      self.current_tab_id=data['source']
      self.screen = self.tabs.get(self.current_tab_id)

      if self.current_tab_id in self.tabsHashMap:
        self.hashMap = dict(self.tabsHashMap[self.current_tab_id])  

        self.read_globals()
        

      if "maintab_"+self.current_tab_id in self.new_tabs:
        self.new_tabs.remove("maintab_"+self.current_tab_id)
      else:   
        current_tab = list(filter(lambda current_tab: current_tab['id'] == self.current_tab_id, self.opened_tabs))
        if len(current_tab)>0:
          self.hashMap['CurrentTabID'] = self.current_tab_id
          self.hashMap['CurrentTabKey'] = current_tab[0].get('key')
          
          self.hashMap['listener']='MainTabSelect'

          self.RunEvent("onWEBMainTabSelected",None,True)
  

      #soup=bs4.BeautifulSoup(features="lxml")
      #layouts =  self.get_layouts(soup,self.screen,0)
      #print(layouts)
                         
      #emit('setvaluehtml', {"key":"root_"+self.current_tab_id,"value":str(layouts)})  


  def set_input(self,method,data,ddata):
   
    try:
      module = __import__('current_handlers')

      #import importlib
      #importlib.reload(module)

    
      jdata = json.loads(data)
    
      jhashMap = javahashMap()
      #jhashMap.importmap(jdata['hashmap'])
      jhashMap.importdict(self.hashMap)
      #f = globals()[func]
      #f = getattr(globals()['handlers'], method)
      f = getattr(module, method)
      res = f(jhashMap,None,ddata)
      jdata['hashmap'] = res.export()
      jdata['stop'] =False
      jdata['ErrorMessage']=""
      jdata['Rows']=[]

      self.hashMap =res.d

      self.write_globals()

      return json.dumps(jdata,ensure_ascii=False)
    except Exception as e:
      #  
      
      self.hashMap['ErrorMessage']= str(e)
       
    

  def set_input_js(self,method,data,ddata,async_mode=False,postExecute=''):
   
    try:
      
      start_time = time.time()
    
      jdata = json.loads(data)
    
      jhashMap = javahashMap()
      #jhashMap.importmap(jdata['hashmap'])
      jhashMap.importdict(self.hashMap)

      handler_id = str(uuid.uuid4().hex)
      if async_mode:
         self.js_results_async[handler_id] = (postExecute,self.current_tab_id)

      self.socket_.emit('eval_js', {"hashMap":jhashMap.d, "script":method,"id":handler_id},room=self.sid,namespace='/'+SOCKET_NAMESPACE) 

      
      if not async_mode:
        while not handler_id in self.js_results:
          pass
        
        result_message = self.js_results[handler_id]
        self.js_results.pop(handler_id, None)

        if result_message.get("code")==1:
          jHashMap = result_message["value"]
          for key, value in jHashMap.items():
              self.hashMap[key]=value

          jhashMap.d = result_message.get("value")
          jdata['hashmap'] = jhashMap.export()
          jdata['stop'] =False
          jdata['ErrorMessage']=""
          jdata['Rows']=[]

        else:
          self.hashMap['ErrorMessage']= result_message.get("value")

      #self.hashMap =res.d

        print("JS eval: --- %s seconds ---" % (time.time() - start_time))  

      return json.dumps(jdata,ensure_ascii=False)
    except Exception as e:
      #  
      
      self.hashMap['ErrorMessage']= str(e)  

    

  def set_input_online(self,operation,json_str):
     

   try:
            headers = {'Content-type': 'application/json; charset=utf-8', 'Accept': 'text/plain'}
            #{'Content-Type': 'application/x-www-form-urlencoded; charset=utf-8'}
            response = requests.post(
            self.urlonline+'/set_input_direct/'+operation,
            data=json_str.encode('utf-8'),
            auth=HTTPBasicAuth(self.username, self.password,),
            headers=headers

            )

   except requests.exceptions.RequestException as e:  
            self.hashMap['ErrorMessage']=str(e)
            return

   if response.status_code==200:
            response.encoding='utf-8'
            
            jresponse = json.loads(response.text.encode("utf-8")) 
           

            if "hashmap" in jresponse:   
                jHashMap = jresponse["hashmap"]
                for valpair in jHashMap:
                    self.hashMap[valpair['key']]=valpair['value']
   else:
      self.hashMap['ErrorMessage']="WebServicw connection error:"+str(response.status_code)

  def RunEvent(self,event,postExecute=None,common=False): 
   
      if common:
        json_str = {"process":"common","operation":"common","hashmap":self.hashMap}
      else:  
        if self.process  ==None:
          return

        json_str = {"process":self.process.get("ProcessName",""),"operation":self.screen.get("Name",""),"hashmap":self.hashMap}

      is_new_handlers = False
      if self.screen!=None:
         if 'Handlers' in self.screen:
            is_new_handlers=True

         
      if is_new_handlers or not (postExecute==None or postExecute=='') or (common and 'CommonHandlers' in self.configuration['ClientConfiguration']):
      #NEW HANDLERS 

        if postExecute==None or  postExecute=='':
          if common:
            handlersArray = self.configuration['ClientConfiguration']['CommonHandlers']
          else:   
            handlersArray = self.screen['Handlers']
        else:  
          handlersArray = json.loads(postExecute)

        for handler in  handlersArray:

          if not event==None:
            if not handler.get('event')==event:
              continue  

          if handler.get('listener')!=None and handler.get('listener')!="":  
             if self.hashMap.get("listener")!=handler.get('listener'):
                continue

          if handler.get('action')=='run':
            if handler.get('type')=='python':
              
              operation = handler.get('method')
              self.set_input(operation,json.dumps(json_str,ensure_ascii=False).encode('utf-8'),self.process_data)

            elif handler.get('type')=='online':
              
              operation = handler.get('method')
              self.set_input_online(operation,json.dumps(json_str,ensure_ascii=False)) 
            elif handler.get('type')=='js':
               self.set_input_js(handler.get("method"),json.dumps(json_str,ensure_ascii=False).encode('utf-8'),self.process_data,False)   

          elif  handler.get('action')=='runasync':
            if handler.get('type')=='python':
            
              operation = handler.get('method')
              
              _thread = threading.Thread(target=self.async_callback_online, args=(operation,json_str,self.current_tab_id,handler.get('postExecute','')))
              _thread.start()   
    
            elif handler.get('type')=='js':
               self.set_input_js(handler.get("method"),json.dumps(json_str,ensure_ascii=False).encode('utf-8'),self.process_data,True,handler.get('postExecute',''))

            elif handler.get('type')=='online':
              
              operation = handler.get('method')

              
              
              _thread = threading.Thread(target=self.async_callback_online, args=(operation,json_str,self.current_tab_id,handler.get('postExecute','')))
              _thread.start()   
    
          

            if handler.get('type')=='online':
              
              operation = handler.get('method')

              
            # thr = threading.Thread(target=self.online_task,args=(operation,json_str))
            # thr.start()
            # print("сразу после")

              #thr.join()
              #print("после joina")

              #self.online_task(operation,json_str)
              #a=''
              #self.set_input_online(operation,json.dumps(json_str,ensure_ascii=False))  

      else:  

        #OLD HANDLERS
      
      

        if event=="onStart":
          if len(self.screen.get('DefOnCreate',''))>0:
            operation = self.screen.get('DefOnCreate','')
            
            #Python
            self.set_input(operation,json.dumps(json_str,ensure_ascii=False).encode('utf-8'),self.process_data)


          if len(self.screen.get('DefOnlineOnCreate',''))>0:
              operation = self.screen.get('DefOnlineOnCreate','')
              
              #Online
              self.set_input_online(operation,json.dumps(json_str,ensure_ascii=False)) 

        if event=="onInput":
          if len(self.screen.get('DefOnInput',''))>0:
            operation = self.screen.get('DefOnInput','')
            
            #Python
            self.set_input(operation,json.dumps(json_str,ensure_ascii=False).encode('utf-8'),self.process_data)


          if len(self.screen.get('DefOnlineOnInput',''))>0:
              operation = self.screen.get('DefOnlineOnInput','')
              
              #Online
              self.set_input_online(operation,json.dumps(json_str,ensure_ascii=False))       

      if len(self.hashMap.get("ErrorMessage",""))>0:
        #print(self.hashMap.get("ErrorMessage",""))       
        self.socket_.emit('error', {'code':self.hashMap.get("ErrorMessage","")},room=self.sid,namespace='/'+SOCKET_NAMESPACE)
    
      try:
        self.handle_command()  
      except Exception as e:
        self.socket_.emit('error', {'code':str(e)},room=self.sid,namespace='/'+SOCKET_NAMESPACE)
        print(e) 
  
  def main_function(self,operation,json_str):
   
    self.set_input(operation,json.dumps(json_str,ensure_ascii=False).encode('utf-8'),self.process_data)
    
  async def run_with_callback(self,operation,json_str,current_tab,postExecute):
    
    self.main_function(operation,json_str)
    
    self.handle_command(current_tab)
    if not (postExecute=='' or postExecute==None):
      self.RunEvent(None,postExecute)

  def async_callback(self,operation,json_str,current_tab,postExecute):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    loop.run_until_complete(self.run_with_callback(operation,json_str,current_tab,postExecute))
    loop.close()

  def main_function_online(self,operation,json_str):
   
    self.set_input_online(operation,json.dumps(json_str,ensure_ascii=False))
    
  async def run_with_callback_online(self,operation,json_str,current_tab,postExecute):
    
    self.main_function_online(operation,json_str)
    
    self.handle_command(current_tab)
    self.RunEvent(None,postExecute)

  def async_callback_online(self,operation,json_str,current_tab,postExecute):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    loop.run_until_complete(self.run_with_callback_online(operation,json_str,current_tab,postExecute))
    loop.close()

  def get_admin_html(self):  

    #path = os.path.dirname(__file__) +os.sep+"templates"+os.sep
    #print(path)
    
    #with open(path+'admin.html', 'r',encoding='utf-8') as file:
    adminhtml="""
    <!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Настройки Simple</title>
  <style>

 
  input[type=text], input[type=password] {
  width: 100%;
  padding: 12px 20px;
  margin: 8px 0;
  display: inline-block;
  border: 1px solid #ccc;
  box-sizing: border-box;
}


button {
  background-color: #04AA6D;
  color: white;
  padding: 14px 20px;
  margin: 8px 0;
  border: none;
  cursor: pointer;
  width: 100%;
}

button:hover {
  opacity: 0.8;
}

  
  .horizontal{
  display: flex;
  flex-direction: row;
  justify-content: begin;
  align-items: center;
  }
  
  .column {
  display: flex;
  flex-direction: column;
  margin: 10px;
  padding: 12px 20px;
  background-color: #F5F5F5;
  
}


.row {
   display: flex;
  flex-direction: row;
}
  
  </style>
  <script src="https://code.jquery.com/jquery-3.5.0.js"></script>
</head>
<body>




<form >

<div class="row">
  <div class="column">
  <h3>Текущая конфигурация</h3>
			
  <label for="uifile">Файл конфигурации(.ui):</label>
  <input type="file" id="uifile" name="uifile"><br><br>
  
  <div class=horizontal>
  <p >Последняя загрузка:</p>
  <p style="color:purple;">16.12.2022 05:28:25</p>
  </div>
 
  </div>
  
  <div class="column">
  
  <h3>Файл локальных обработчиков (Python)</h3>

  <label for="handlersfile">Файл обработчиков(.py):</label>
  <input type="file" id="handlersfile" name="handlersfile"><br><br>
  
    <div class=horizontal>
  <p >Последняя загрузка:</p>
  <p style="color:purple;">09.12.2022 05:33:41</p>
  </div>
  
  </div>
</div>




 
  
</form>



<form>

<h3>Параметры доступа к online-обработчикам (бек-система)</h3>
<label for="url">URL:</label>
  <input type="text" id="url" name="url" value= ><br><br>
<label for="user">Пользователь:</label>
  <input type="text" id="user" name="user" value=><br><br>  
<label for="password">Пароль:</label>
  <input type="password" id="password" name="password" value=><br><br>

</form>


<button   onclick="SaveSettings()">Сохранить настройки</button>

<script>
$(document).ready(function() {
    $('#uifile').change(function(evt) {
       UploadFilesUI()
    });
});
</script>

<script>
$(document).ready(function() {
    $('#handlersfile').change(function(evt) {
       UploadFilesHandlers()
    });
});
</script>

<script>
async function UploadFilesUI() 
{
	
	
	if($('#uifile').val().length == 0){
    alert("Нужно указать файл конфигурации");
   
    return false;
    }else{

    let formData = new FormData();
    let ui = $('#uifile').prop('files')[0];   
         
    formData.append("uifile", ui);
	  
    const ctrl = new AbortController()   
    setTimeout(() => ctrl.abort(), 5000);
    
    try {
       let r = await fetch('/uploader', 
         {method: "POST", body: formData, signal: ctrl.signal}); 
		 location.reload();  
        
       console.log('HTTP response code:',r.status); 
    } catch(e) {
       console.log('Some problem...:', e);
    }
	}
    
}
</script>

<script>
  async function UploadFilesHandlers() 
  {
    
    
    if($('#handlersfile').val().length == 0){
      alert("Нужно указать файл обработчиков");
     
      return false;
      }else{
  
      let formData = new FormData();
       let handlers = $('#handlersfile').prop('files')[0];  	
           
    formData.append("handlersfile", handlers);
      
      const ctrl = new AbortController()   
      setTimeout(() => ctrl.abort(), 5000);
      
      try {
         let r = await fetch('/uploader', 
           {method: "POST", body: formData, signal: ctrl.signal}); 
         location.reload();  
        
      } catch(e) {
         console.log('Some problem...:', e);
      }
    }
      
  }
  </script>

<script>
async function SaveSettings() 
{
	
	
	
    let settings = { url:$('#url').val(), user:$('#user').val(), password:$('#password').val() };
    let formData = new FormData();
           
    formData.append("settings", JSON.stringify(settings)); 
    
    const ctrl = new AbortController()    
    setTimeout(() => ctrl.abort(), 5000);
    
    try {
       let r = await fetch('/uploader', 
         {method: "PUT", body: formData, signal: ctrl.signal}); 
       
        document.location.href = '../';
    } catch(e) {
       console.log('Some problem...:', e);
    }
	
    
}
</script>
</body>
</html>
    """

    return html.unescape(adminhtml)

  def load_settings(self,path):  
    fullpath = Simple.PYTHONPATH+os.sep+ path

    path = pathlib.Path(fullpath)
    if path.is_file():
        f = open(fullpath)
        websettings = json.load(f)
        if 'url' in websettings:
            self.urlonline=websettings.get("url","")
        if 'user' in websettings:
            self.username=websettings.get("user","")
        if 'password' in websettings:
            self.password=websettings.get("password","") 

  def write_settings_value(self,key,value,path):
     fullpath = Simple.PYTHONPATH+os.sep+ path
     fullpath = pathlib.Path(fullpath)
     if fullpath.is_file():
        f = open(fullpath)
        websettings = json.load(f)  
        websettings[key]=value
     else:
        websettings={}   
        websettings[key]=value

     with open(fullpath, 'w') as outfile:
            json.dump(websettings, outfile) 
    
  def write_settings(self,request,path):  

      if request.method == 'POST':
    
        if 'uifile' in request.files:
          f = request.files['uifile']
          f.save(Simple.PYTHONPATH+os.sep+'current_configuration.ui')
          self.write_settings_value("last_update_uifile",datetime.now().strftime("%d.%m.%Y %H:%M:%S"),path)
        
          return "ok",200

        if 'handlersfile' in request.files:
          f = request.files['handlersfile']
          f.save(Simple.PYTHONPATH+os.sep+'current_handlers.py')
          self.write_settings_value("last_update_handlersfile",datetime.now().strftime("%d.%m.%Y %H:%M:%S"),path)

          return "ok",200
    
      if request.method == 'PUT':

          settings = json.loads(request.form.get('settings'))
          
          fullpath = Simple.PYTHONPATH+os.sep+ path
          
          fullpath = pathlib.Path(fullpath)
          if fullpath.is_file():
            f = open(fullpath)
            websettings = json.load(f)
          else:    
            websettings ={}

          for key, value in settings.items():
                    websettings[key]=value

          with open(fullpath, 'w') as outfile:
              json.dump(websettings, outfile)                  
      
        
  

class javahashMap:
        d = {}
        def put(self,key,val):
            self.d[key]=val
        def get(self,key):
            return self.d.get(key)
        def remove(self,key):
            if key in self .d:
                self.d.pop(key)
        def containsKey(self,key):
            return  key in self.d
        def importmap(self,arr):
            self.d={}
            for pair in arr:
                self.d[pair['key']]=pair['value']
        def importdict(self,d):
            self.d=d
                
        def export(self):
            ex_hashMap = []
            for key in self.d.keys():
                ex_hashMap.append({"key":key,"value":self.d[key]})
            return ex_hashMap
     